"""Optional AI phrasing for engagement replies — evidence-first, never inventive.

The model is only allowed to rephrase the already-grounded template text (built from
verified property facts) more warmly and conversationally. It must not add prices,
dates, amenities, or contact details that are not already present, and it must keep
links and phone numbers verbatim. If the key is missing or the call fails, the caller
falls back to the deterministic template — AI is a nicety, never a dependency.
"""
from __future__ import annotations

from app import settings

_SYSTEM = (
    "You write SHORT, warm Instagram replies for a real-estate page. "
    "Use ONLY the facts in the 'Details' block below — never invent or change prices, "
    "dates, amenities, locations, links, or phone numbers. Keep every URL and phone "
    "number EXACTLY as given. Keep it under 480 characters, friendly, with one clear "
    "call to action. No hashtags. Do not add facts that are not in Details."
)


def draft_reply(grounded_text: str, inbound_text: str, username: str) -> str:
    """Return an LLM-phrased reply grounded on `grounded_text`. Raises on any problem
    so the ResponseProvider can fall back to the deterministic template."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    from openai import OpenAI
    from app.services.llm import _is_reasoning_model
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user = (f"Commenter @{username or 'user'} wrote: {inbound_text or '(no text)'!r}\n\n"
            f"Details you may use (do not go beyond these):\n{grounded_text}")
    kwargs = {"model": settings.OPENAI_MODEL,
              "messages": [{"role": "system", "content": _SYSTEM},
                           {"role": "user", "content": user}]}
    # Newer reasoning models reject max_tokens/temperature; use max_completion_tokens.
    if _is_reasoning_model(settings.OPENAI_MODEL):
        kwargs["max_completion_tokens"] = 400
        if settings.LLM_REASONING_EFFORT:
            kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT
    else:
        kwargs["max_tokens"] = 320
        kwargs["temperature"] = 0.5
    resp = client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()
