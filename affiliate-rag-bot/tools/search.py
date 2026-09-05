"""
tools/search.py  —  Tavily-powered trend discovery.

Searches for what's actually trending in the product category right now,
so the AI can weave real keywords into pin descriptions.
"""
from __future__ import annotations
import re
from typing import Optional

from tavily import TavilyClient

from config import cfg
from utils.logger import log


_client: Optional[TavilyClient] = None

def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=cfg.tavily_api_key)
    return _client


async def fetch_trending_keywords(category: str, marketplace: str = "amazon.in") -> list[str]:
    """
    Uses Tavily to search for trending products & keywords in the category.
    Returns a deduplicated list of keywords to inject into pin descriptions.
    """
    query = f"trending {category} products {marketplace} 2025 best sellers popular"

    log.step(f"[Tavily] Searching trends: '{query}'...")

    try:
        client  = _get_client()
        results = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

        keywords: set[str] = set()

        # Extract from AI answer
        if results.get("answer"):
            keywords.update(_extract_keywords(results["answer"]))

        # Extract from result snippets
        for result in results.get("results", []):
            if result.get("content"):
                keywords.update(_extract_keywords(result["content"]))

        # Always add some Pinterest-standard keywords
        keywords.update([f"best {category}", f"{category} ideas", f"trending {category}"])

        kw_list = sorted(keywords)[:15]
        log.success(f"[Tavily] Found {len(kw_list)} trending keywords")
        return kw_list

    except Exception as e:
        log.warning(f"[Tavily] Search failed: {e} — using fallback keywords")
        return _fallback_keywords(category)


def _extract_keywords(text: str) -> list[str]:
    """Pull out useful noun phrases from search text."""
    # Simple extraction: 2-4 word phrases that look like product keywords
    text = text.lower()
    # Remove punctuation except hyphens
    text = re.sub(r"[^\w\s\-]", " ", text)
    words = text.split()

    keywords = []
    for i, word in enumerate(words):
        if len(word) > 4 and word not in STOP_WORDS:
            # Single meaningful word
            keywords.append(word)
            # Bigram
            if i + 1 < len(words) and len(words[i+1]) > 3 and words[i+1] not in STOP_WORDS:
                keywords.append(f"{word} {words[i+1]}")

    return list(set(keywords))[:20]


def _fallback_keywords(category: str) -> list[str]:
    defaults = {
        "home":        ["home decor", "living room ideas", "cozy home", "interior design", "home essentials"],
        "fashion":     ["outfit ideas", "style inspo", "trending fashion", "wardrobe essentials", "fashion finds"],
        "kitchen":     ["kitchen gadgets", "cooking essentials", "kitchen organization", "meal prep", "food storage"],
        "electronics": ["tech gadgets", "smart home", "best electronics", "gadget review", "tech deals"],
        "beauty":      ["skincare routine", "beauty essentials", "makeup tips", "self care", "glow up"],
    }
    return defaults.get(category, ["trending products", "best deals", "must have", "gift ideas", "top rated"])


STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "are", "from", "have",
    "been", "will", "your", "our", "their", "here", "there", "when",
    "where", "what", "which", "into", "than", "then", "they", "them",
    "these", "those", "also", "more", "some", "such", "very", "just",
    "about", "after", "before", "because", "while", "under", "over",
}
