"""LLM content generation — OpenAI gpt-4o-mini, ONE batched call per request.

Why one call: every request carries a fixed instruction overhead (the schema +
rules). Making N separate calls pays that overhead N times. Batching all posts
and slides into a single structured JSON response amortises the input cost once
across the whole batch and bounds the (4x more expensive) output via max_tokens.
The token usage of each call is returned so the UI can show the input:output
ratio.  See README "Token economics".
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app import settings
from app.appconfig import load_config
from app.services import emojis

_client = None


class LLMError(RuntimeError):
    pass


def _get_client():
    global _client
    if not settings.OPENAI_API_KEY:
        raise LLMError(
            "OPENAI_API_KEY is not set in .env. Add it and restart the server."
        )
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


_SYSTEM = (
    "You are a senior Instagram content strategist and copywriter. "
    "You ALWAYS respond with strict, valid JSON only — no markdown, no prose "
    "outside the JSON. You write original content and never attribute quotes to "
    "famous people."
)


def _quotes_prompt(
    posts: int, slides: int, topic: Optional[str],
    min_words: int, max_words: int, max_tags: int, avoid_quotes: List[str],
) -> str:
    about = f" about: {topic}" if topic else ""
    avoid = ""
    if avoid_quotes:
        joined = "; ".join(q.strip() for q in avoid_quotes if q.strip())
        avoid = (
            "\nDo NOT reuse or closely paraphrase any of these already-posted quotes:\n"
            f"{joined}\n"
        )
    return (
        f"Create {posts} Instagram CAROUSEL posts for a motivational quotes page{about}.\n"
        f"Each post is a carousel of {slides} slides around ONE cohesive theme.\n"
        "For each post return these fields:\n"
        '- "title": 2-4 word internal label\n'
        '- "theme": the central idea in a few words\n'
        '- "image_query": 3-6 word visual phrase for an aesthetic background photo\n'
        '- "caption": 1-3 sentence engaging caption with 1-2 natural emojis, NO hashtags inside\n'
        f'- "hashtags": {max_tags} lowercase relevant hashtags WITHOUT the # symbol\n'
        f'- "slides": array of EXACTLY {slides} objects, each with:\n'
        '    "heading": <=4 word punchy heading (slide 1 must be a scroll-stopping hook),\n'
        f'    "body": an ORIGINAL short quote, {min_words}-{max_words} words, no author, no emojis, no hashtags,\n'
        '    "footnote": a short tag or ""\n'
        "Rules: original content only; vary the themes across posts; "
        "slide bodies must be emoji-free and hashtag-free."
        f"{avoid}\n"
        'Return JSON shaped exactly as: {"posts":[ {...} ]}'
    )


def _news_prompt(posts: int, slides: int, items: List[Dict[str, str]]) -> str:
    compact = [
        {
            "title": it.get("title", "")[:200],
            "summary": it.get("summary", "")[:320],
            "source": it.get("source", ""),
        }
        for it in items[: max(posts * 2, posts)]
    ]
    return (
        f"You are given REAL news items as JSON. Turn the {posts} most newsworthy of "
        "them into Instagram CAROUSEL infographics.\n"
        "Ground EVERY claim only in the provided items — do not invent facts, numbers, "
        "or names.\n"
        f"Each post = ONE story expanded into EXACTLY {slides} slides.\n"
        "For each post return:\n"
        '- "title": short internal label\n'
        '- "source": the publisher name from the item\n'
        '- "image_query": a 2-4 word visual backdrop theme for the story '
        '(e.g. "middle east diplomacy", "california wildfire", "stock market")\n'
        '- "caption": 1-2 sentence neutral summary with 1-2 natural emojis, NO hashtags inside\n'
        '- "hashtags": 8-12 lowercase hashtags WITHOUT the # symbol\n'
        f'- "slides": EXACTLY {slides} objects, each with "heading", "body", "footnote":\n'
        '    slide 1 -> heading = hook (<=5 words), body = the headline rephrased clearly,\n'
        "    middle slides -> heading = 2-3 word label, body = one key point (<=22 words),\n"
        '    final slide -> heading = "Takeaway", body = a one-sentence takeaway,\n'
        '    every slide "footnote" = the source name.\n'
        "Keep slide bodies emoji-free and hashtag-free.\n"
        'Return JSON shaped exactly as: {"posts":[ {...} ]}\n\n'
        f"News items:\n{json.dumps(compact, ensure_ascii=False)}"
    )


def _clean_hashtags(raw: Any, limit: int = 12) -> List[str]:
    tags: List[str] = []
    seen = set()
    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw)
    if not isinstance(raw, list):
        return tags
    for t in raw:
        if not isinstance(t, str):
            continue
        tag = "#" + re.sub(r"[^a-z0-9]", "", t.lower().lstrip("#"))
        if tag != "#" and tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _normalize_post(raw: Dict[str, Any], slides: int, max_tags: int = 12) -> Dict[str, Any]:
    caption = str(raw.get("caption", "")).strip()
    # If the model returned a caption with no emoji, add one subtle, relevant emoji.
    has_emoji = emojis.strip_emojis(caption) != caption
    if caption and not has_emoji:
        extra = emojis.pick_for_text(raw.get("theme", "") or caption, k=1)
        if extra:
            caption = f"{caption} {extra}"

    out_slides: List[Dict[str, str]] = []
    for s in (raw.get("slides") or [])[:slides]:
        if not isinstance(s, dict):
            continue
        out_slides.append(
            {
                "heading": str(s.get("heading", "")).strip(),
                "body": emojis.strip_emojis(str(s.get("body", "")).strip()),
                "footnote": str(s.get("footnote", "")).strip(),
            }
        )
    return {
        "title": str(raw.get("title", "")).strip() or "Post",
        "theme": str(raw.get("theme", "")).strip(),
        "source": str(raw.get("source", "")).strip(),
        "image_query": str(raw.get("image_query", "")).strip(),
        "caption": caption,
        "hashtags": _clean_hashtags(raw.get("hashtags"), limit=max_tags),
        "slides": out_slides,
    }


def generate_batch(
    *,
    niche: str,
    posts: int,
    slides: int,
    topic: Optional[str] = None,
    news_items: Optional[List[Dict[str, str]]] = None,
    avoid_quotes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """One LLM call. Returns {"posts": [...], "usage": {...}, "model": str}."""
    cfg = load_config()
    max_tags = int(cfg["hashtags"]["max_dynamic"])
    if niche == "news":
        user_prompt = _news_prompt(posts, slides, news_items or [])
        temperature = 0.5
    else:
        user_prompt = _quotes_prompt(
            posts, slides, topic,
            int(cfg["quote"]["min_words"]), int(cfg["quote"]["max_words"]),
            max_tags, avoid_quotes or [],
        )
        temperature = 0.85

    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        )
    except Exception as exc:  # network / auth / rate limit
        raise LLMError(f"OpenAI request failed: {exc}") from exc

    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise LLMError("Model did not return valid JSON.")
        data = json.loads(match.group(0))

    raw_posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(raw_posts, list) or not raw_posts:
        raise LLMError("Model returned no posts.")

    normalized = [_normalize_post(p, slides, max_tags) for p in raw_posts[:posts] if isinstance(p, dict)]
    normalized = [p for p in normalized if p["slides"]]
    if not normalized:
        raise LLMError("Model returned posts without slides.")

    usage = resp.usage
    return {
        "posts": normalized,
        "model": settings.OPENAI_MODEL,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
            # input:output ratio — see README "Token economics"
            "io_ratio": round(
                getattr(usage, "prompt_tokens", 0)
                / max(1, getattr(usage, "completion_tokens", 0)),
                2,
            ),
        },
    }
