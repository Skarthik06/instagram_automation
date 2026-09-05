"""LLM provider abstraction (Spec §5).

The platform must NOT hard-code a single vendor. All reasoning/marketing/copy and
semantic-validation calls go through `LLMProvider`, so the model is swappable. The
default `OpenAIProvider` is model-aware (reasoning vs classic) and reuses the exact
contract already proven in `app/services/llm.py` (gpt-5-nano, minimal reasoning).

A tiny content-addressed cache (keyed by model+prompt hash) satisfies the Cost
Governor's "never re-spend on identical input" rule (Spec §28).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app import settings
from app.services.llm import _is_reasoning_model  # single source of truth

_CACHE_DIR = settings.BASE_DIR / "images" / "business" / "_llm_cache"


class ProviderError(RuntimeError):
    pass


# ---- usage/trace accounting (observability, Spec §4) --------------------
class Usage:
    def __init__(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.reasoning_tokens = 0
        self.cache_hits = 0

    def add(self, u: Any, cached: bool = False) -> None:
        self.calls += 1
        if cached:
            self.cache_hits += 1
            return
        self.prompt_tokens += getattr(u, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(u, "completion_tokens", 0) or 0
        det = getattr(u, "completion_tokens_details", None)
        self.reasoning_tokens += (getattr(det, "reasoning_tokens", 0) or 0) if det else 0

    def as_dict(self) -> Dict[str, int]:
        # gpt-5-nano pricing (per 1M): $0.05 in / $0.40 out.
        cost = (self.prompt_tokens * 0.05 + self.completion_tokens * 0.40) / 1_000_000
        return {
            "llm_calls": self.calls,
            "cache_hits": self.cache_hits,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "est_cost_usd": round(cost, 6),
        }


class LLMProvider(ABC):
    """Vendor-agnostic interface. Implementations wrap a concrete API."""

    @abstractmethod
    def structured_output(self, *, system: str, user: str,
                          max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Return parsed JSON object from a strict-JSON model response."""

    @abstractmethod
    def analyze(self, *, system: str, user: str,
                max_tokens: Optional[int] = None) -> str:
        """Return free-form text (still no fact invention — caller grounds it)."""

    @abstractmethod
    def classify_image(self, *, image_bytes: bytes, mime: str,
                       labels: List[str], instruction: str) -> Dict[str, Any]:
        """Vision: pick the best label for an image. Returns {label, confidence}."""


class OpenAIProvider(LLMProvider):
    def __init__(self, model: Optional[str] = None, usage: Optional[Usage] = None) -> None:
        self.model = model or settings.OPENAI_MODEL
        self.usage = usage or Usage()
        self._client = None
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # -- internals ---------------------------------------------------------
    def _c(self):
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ProviderError("OPENAI_API_KEY is not set.")
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def _cache_path(self, key: str) -> Path:
        return _CACHE_DIR / f"{key}.json"

    def _hash(self, *parts: str) -> str:
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode("utf-8"))
        return h.hexdigest()[:32]

    def _chat(self, messages: List[Dict[str, Any]], *, json_mode: bool,
              max_tokens: Optional[int], cache_key: Optional[str]) -> str:
        if cache_key:
            cp = self._cache_path(cache_key)
            if cp.exists():
                self.usage.add(None, cached=True)
                return json.loads(cp.read_text(encoding="utf-8"))["content"]

        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        cap = max_tokens or settings.LLM_MAX_OUTPUT_TOKENS
        if _is_reasoning_model(self.model):
            kwargs["max_completion_tokens"] = cap
            if settings.LLM_REASONING_EFFORT:
                kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT
        else:
            kwargs["max_tokens"] = cap
            kwargs["temperature"] = 0.4

        try:
            resp = self._c().chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"LLM request failed: {exc}") from exc

        self.usage.add(resp.usage)
        content = resp.choices[0].message.content or ""
        if cache_key:
            self._cache_path(cache_key).write_text(
                json.dumps({"content": content}), encoding="utf-8"
            )
        return content

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ProviderError("Model did not return JSON.")
            return json.loads(m.group(0))

    # -- interface ---------------------------------------------------------
    def structured_output(self, *, system: str, user: str,
                          max_tokens: Optional[int] = None) -> Dict[str, Any]:
        key = self._hash("struct", self.model, system, user)
        return self._parse_json(self._chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            json_mode=True, max_tokens=max_tokens, cache_key=key,
        ))

    def analyze(self, *, system: str, user: str,
                max_tokens: Optional[int] = None) -> str:
        key = self._hash("analyze", self.model, system, user)
        return self._chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            json_mode=False, max_tokens=max_tokens, cache_key=key,
        )

    def classify_image(self, *, image_bytes: bytes, mime: str,
                       labels: List[str], instruction: str) -> Dict[str, Any]:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        key = self._hash("vision", self.model, instruction, ",".join(labels),
                         hashlib.sha256(image_bytes).hexdigest()[:16])
        system = ("You classify a single real-estate document image into exactly one "
                  "label from the allowed set. Respond with strict JSON "
                  '{"label": <one of allowed>, "confidence": 0..1}. If unsure use '
                  '"unknown".')
        user_content = [
            {"type": "text", "text": f"{instruction}\nAllowed labels: {labels}"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
        cp = self._cache_path(key)
        if cp.exists():
            self.usage.add(None, cached=True)
            return json.loads(cp.read_text(encoding="utf-8"))
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user_content}],
            "response_format": {"type": "json_object"},
        }
        if _is_reasoning_model(self.model):
            kwargs["max_completion_tokens"] = 400
            if settings.LLM_REASONING_EFFORT:
                kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT
        else:
            kwargs["max_tokens"] = 200
        try:
            resp = self._c().chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            # Vision is a bounded fallback — degrade to 'unknown', never crash.
            return {"label": "unknown", "confidence": 0.0, "error": str(exc)}
        self.usage.add(resp.usage)
        out = self._parse_json(resp.choices[0].message.content or "{}")
        label = out.get("label", "unknown")
        if label not in labels:
            label = "unknown"
        result = {"label": label, "confidence": float(out.get("confidence", 0.0) or 0.0)}
        cp.write_text(json.dumps(result), encoding="utf-8")
        return result


def get_provider(usage: Optional[Usage] = None) -> LLMProvider:
    """Factory — swap here to change vendor platform-wide."""
    return OpenAIProvider(usage=usage)
