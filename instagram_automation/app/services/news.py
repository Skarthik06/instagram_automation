"""News sourcing for the News niche.

Primary source is Google News RSS (no key, no rate limit, $0). If a News API
key has been saved in the rags Settings panel, it is used instead with an
automatic fallback to RSS on any error. Returned items are plain text (HTML
stripped) so they can be fed straight into the single LLM call as grounding.
"""
from __future__ import annotations

import html
import re
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import requests

from app import rags

_GOOGLE_SEARCH = (
    "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
)
_GOOGLE_TOP = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
_TAG_RE = re.compile(r"<[^>]+>")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; InstaNewsBot/1.0)"}


def _clean(text: str) -> str:
    if not text:
        return ""
    return _TAG_RE.sub("", html.unescape(text)).strip()


def _source_from_entry(entry, fallback_title: str) -> str:
    src = getattr(entry, "source", None)
    if src and getattr(src, "title", None):
        return src.title
    # Google News titles are often "Headline - Publisher"
    if " - " in fallback_title:
        return fallback_title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def _from_rss(topic: Optional[str], limit: int) -> List[Dict[str, str]]:
    url = _GOOGLE_SEARCH.format(q=quote_plus(topic)) if topic else _GOOGLE_TOP
    feed = feedparser.parse(url)
    items: List[Dict[str, str]] = []
    for entry in feed.entries[:limit]:
        title = _clean(getattr(entry, "title", ""))
        if not title:
            continue
        # Strip the trailing " - Publisher" from the headline for cleaner text.
        headline = title.rsplit(" - ", 1)[0].strip() if " - " in title else title
        items.append(
            {
                "title": headline,
                "summary": _clean(getattr(entry, "summary", "")) or headline,
                "source": _source_from_entry(entry, title),
                "link": getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
            }
        )
    return items


def _from_newsapi(key: str, topic: Optional[str], limit: int) -> List[Dict[str, str]]:
    if topic:
        url = "https://newsapi.org/v2/everything"
        params = {"q": topic, "language": "en", "sortBy": "publishedAt", "pageSize": limit}
    else:
        url = "https://newsapi.org/v2/top-headlines"
        params = {"language": "en", "pageSize": limit, "country": "us"}
    params["apiKey"] = key
    resp = requests.get(url, params=params, headers=_UA, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "News API error"))
    items: List[Dict[str, str]] = []
    for art in data.get("articles", [])[:limit]:
        title = _clean(art.get("title", ""))
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": _clean(art.get("description") or art.get("content") or title),
                "source": (art.get("source") or {}).get("name", "News"),
                "link": art.get("url", ""),
                "published": art.get("publishedAt", ""),
            }
        )
    return items


def fetch_news(topic: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Return up to `limit` news items, newest/most-relevant first."""
    key = (rags.get_setting("news_api_key") or "").strip()
    if key:
        try:
            items = _from_newsapi(key, topic, limit)
            if items:
                return items
        except Exception as exc:  # fall back to RSS, never hard-fail here
            print(f"[news] News API failed ({exc}); falling back to RSS")
    return _from_rss(topic, limit)
