"""File-based tuning via `config.json` (optional, advanced).

UI-editable settings live in the rags store; this file is for the deeper
styling/generation knobs the old project exposed through `config.json`:
overlay look, quote word limits, hashtag counts, dedup depth. Missing keys
fall back to these defaults, so `config.json` is entirely optional.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Dict

from app.settings import BASE_DIR, DEFAULT_HANDLE

CONFIG_FILE = BASE_DIR / "config.json"

DEFAULTS: Dict[str, Any] = {
    "quote": {
        "min_words": 6,
        "max_words": 16,
        "dedupe_history": 24,   # how many recent posted quotes to avoid repeating
    },
    "hashtags": {
        "max_dynamic": 12,      # LLM hashtags kept per post
        "fixed": [],            # appended to every caption (rags setting overrides)
    },
    "overlay": {
        "handle": DEFAULT_HANDLE,
        "position": "center",   # top | center | bottom (quote text block)
        "darkness": 0.42,       # 0..1 background dim for legibility
        "text_color": "#ffffff",
    },
}


def _deep_merge(base: dict, override: Mapping) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> Dict[str, Any]:
    """Re-read on each call so edits to config.json apply without a restart."""
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = _deep_merge(cfg, json.load(f))
        except Exception as exc:  # noqa: BLE001
            print(f"[config] failed to read config.json: {exc}; using defaults")
    return cfg
