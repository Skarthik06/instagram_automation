"""Orchestration: niche -> batch of carousel previews -> publish.

Generation makes exactly ONE LLM call for the whole batch, renders slides
locally and serves them as previews (no git push yet). Publishing a chosen
post pushes only that post's slides to GitHub and posts the carousel to the
selected account.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import db, rags, settings
from app.appconfig import load_config
from app.services import hosting, instagram, llm, news, render, scraper

# In-memory store of pending (un-published) batches.
_BATCHES: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fixed_hashtags() -> List[str]:
    """Brand hashtags: rags setting takes priority, else config.json hashtags.fixed."""
    raw = (rags.get_setting("fixed_hashtags") or "").strip()
    items = re.split(r"[\s,]+", raw) if raw else load_config()["hashtags"].get("fixed", [])
    return [t for t in items if t]


def _compose_caption(post: Dict[str, Any], niche: str, fixed_tags: List[str]) -> str:
    """Final caption: lead quote (quotes only) + body + LLM hashtags + fixed hashtags."""
    tags, seen = [], set()
    for t in list(post["hashtags"]) + list(fixed_tags):
        tag = t if t.startswith("#") else "#" + re.sub(r"[^a-z0-9]", "", t.lower().lstrip("#"))
        if tag != "#" and tag not in seen:
            seen.add(tag)
            tags.append(tag)

    body = post["caption"]
    if niche == "quotes" and post["slides"]:
        lead = (post["slides"][0].get("body") or "").strip()
        if lead:
            body = f'"{lead}"\n\n{post["caption"]}'

    return f"{body}\n\n{' '.join(tags)}" if tags else body


def _public_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """Strip local filesystem paths before sending to the frontend."""
    return {
        "index": post["index"],
        "title": post["title"],
        "caption": post["caption"],
        "caption_full": post["caption_full"],
        "hashtags": post["hashtags"],
        "slides": post["slides"],
        "source": post["source"],
        "preview_urls": post["preview_urls"],
        "published": post["published"],
        "result": post["result"],
    }


def public_batch(batch: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "batch_id": batch["id"],
        "niche": batch["niche"],
        "created_at": batch["created_at"],
        "model": batch["model"],
        "usage": batch["usage"],
        "posts": [_public_post(p) for p in batch["posts"]],
    }


async def generate(
    *, niche: str, posts: Optional[int] = None, slides: Optional[int] = None,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    niche = niche if niche in settings.NICHES else "quotes"
    posts = posts or rags.get_int_setting("posts_per_batch", settings.DEFAULT_POSTS_PER_BATCH, 1, settings.MAX_POSTS_PER_BATCH)
    slides = slides or rags.get_int_setting("slides_per_post", settings.DEFAULT_SLIDES_PER_POST, 1, settings.MAX_SLIDES_PER_POST)

    # Multi-machine: catch up on what another laptop published before we start,
    # so the eventual publish-push has little/nothing to reconcile. Best-effort.
    try:
        hosting.sync()
    except Exception as exc:
        print(f"[generator] repo sync skipped: {exc}")

    news_items: List[Dict[str, str]] = []
    if niche == "news":
        news_items = news.fetch_news(topic=topic, limit=max(posts * 2, posts))
        if not news_items:
            raise RuntimeError("No news could be fetched. Try a different topic.")

    # quotes: avoid repeating recently-posted quotes (bounded for token cost)
    avoid_quotes: List[str] = []
    used_norms: set = set()
    if niche == "quotes":
        history_depth = int(load_config()["quote"]["dedupe_history"])
        avoid_quotes = db.get_recent_quote_texts(limit=history_depth)
        used_norms = db.get_used_quote_norms()

    # ---- the single LLM call ----
    result = llm.generate_batch(
        niche=niche, posts=posts, slides=slides, topic=topic,
        news_items=news_items, avoid_quotes=avoid_quotes,
    )

    batch_id = uuid.uuid4().hex
    out_dir = settings.PREVIEWS_DIR
    fixed_tags = _fixed_hashtags()
    seen_in_batch: set = set()

    built_posts: List[Dict[str, Any]] = []
    for i, post in enumerate(result["posts"]):
        # hard de-dup guard: drop slide quotes already used (history or this batch)
        if niche == "quotes":
            kept = []
            for s in post["slides"]:
                norm = db.normalize_quote(s.get("body", ""))
                if not norm or norm in used_norms or norm in seen_in_batch:
                    continue
                seen_in_batch.add(norm)
                kept.append(s)
            if kept:  # keep originals only if everything was a duplicate (rare)
                post["slides"] = kept

        # Both niches now get scraped backgrounds (quotes: aesthetic photo;
        # news: a moody backdrop for the infographic, with a heavy dark overlay).
        background_urls: List[str] = []
        query = (post.get("image_query") or post.get("theme")
                 or post.get("title") or "aesthetic minimal background")
        try:
            scraped = await scraper.scrape_backgrounds(
                f"{query} aesthetic background", limit=max(slides + 2, 6)
            )
            background_urls = [s["url"] for s in scraped]
            # Top up with a broad query so every slide gets a DISTINCT background
            # (otherwise a narrow query repeats one image or falls back to gradient).
            if len(background_urls) < slides:
                for fb in ("minimal aesthetic gradient wallpaper",
                           "calm nature aesthetic background"):
                    if len(background_urls) >= slides:
                        break
                    extra = await scraper.scrape_backgrounds(fb, limit=slides * 2)
                    for s in extra:
                        if s["url"] not in background_urls:
                            background_urls.append(s["url"])
                        if len(background_urls) >= slides:
                            break
        except Exception as exc:
            print(f"[generator] background scrape failed for post {i}: {exc}")

        slide_paths = render.render_post_slides(
            post=post, niche=niche, out_dir=out_dir, post_id=f"{batch_id[:8]}_{i}",
            background_urls=background_urls, palette_idx=i,
        )
        caption_full = _compose_caption(post, niche, fixed_tags)

        built_posts.append(
            {
                "index": i,
                "title": post["title"],
                "caption": post["caption"],
                "caption_full": caption_full,
                "hashtags": post["hashtags"],
                "slides": post["slides"],
                "source": post.get("source", ""),
                "slide_paths": slide_paths,
                "preview_urls": [hosting.preview_url(p) for p in slide_paths],
                "published": False,
                "result": None,
            }
        )

    batch = {
        "id": batch_id,
        "niche": niche,
        "created_at": _now(),
        "model": result["model"],
        "usage": result["usage"],
        "posts": built_posts,
    }
    _BATCHES[batch_id] = batch
    return public_batch(batch)


def publish(*, batch_id: str, post_index: int, account_id: int) -> Dict[str, Any]:
    batch = _BATCHES.get(batch_id)
    if not batch:
        raise RuntimeError("Batch not found or expired. Generate again.")
    if post_index < 0 or post_index >= len(batch["posts"]):
        raise RuntimeError("Invalid post index.")
    post = batch["posts"][post_index]
    if post["published"]:
        raise RuntimeError("This post was already published.")

    account = rags.get_account(account_id, with_secret=True)
    if not account:
        raise RuntimeError("Account not found.")
    if not account.get("is_active"):
        raise RuntimeError(f"Account '{account.get('label')}' is disabled.")

    # 1) host slides publicly, 2) publish to Instagram, 3) record history
    raw_urls = hosting.publish_images(
        post["slide_paths"], commit_msg=f"Add {batch['niche']} carousel ({post['title']})"
    )
    ig_result = instagram.publish(account, raw_urls, post["caption_full"])

    db.save_published_post(
        account_id=account["id"],
        account_label=account["label"],
        niche=batch["niche"],
        caption=post["caption_full"],
        media_type=ig_result["media_type"],
        ig_media_id=ig_result["ig_media_id"],
        permalink=ig_result.get("permalink"),
        cover_url=raw_urls[0] if raw_urls else None,
        slide_urls=raw_urls,
    )

    # remember posted quotes so future generations don't repeat them
    if batch["niche"] == "quotes":
        db.add_used_quotes([s.get("body", "") for s in post["slides"]])

    post["published"] = True
    post["result"] = {
        "permalink": ig_result.get("permalink"),
        "media_type": ig_result["media_type"],
        "account": account["label"],
    }
    return post["result"]


def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    batch = _BATCHES.get(batch_id)
    return public_batch(batch) if batch else None
