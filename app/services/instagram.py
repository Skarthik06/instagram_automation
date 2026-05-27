"""Instagram Graph API publisher — multi-account, single image + carousel.

Each call receives a full account record (with its own business id + token)
from the rags store, so multiple accounts can be posted to independently.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import requests

GRAPH = "https://graph.facebook.com/v24.0"


class InstagramError(RuntimeError):
    pass


def _looks_like_placeholder(token: Optional[str]) -> bool:
    if not token:
        return True
    low = token.strip().lower()
    if len(low) < 80:
        return True
    return any(m in low for m in ("token_here", "your_", "replace", "<", ">", "xxx"))


def _validate(account: Dict) -> None:
    if _looks_like_placeholder(account.get("ig_access_token")):
        raise InstagramError(
            f"Account '{account.get('label')}' has a missing/placeholder access token. "
            "Set a valid Instagram Graph token in the Settings panel."
        )
    biz = str(account.get("ig_business_id") or "")
    if not biz.isdigit():
        raise InstagramError(
            f"Account '{account.get('label')}' has an invalid Business ID "
            f"({biz!r}); it must be the numeric IG Business Account ID."
        )


def _post(url: str, data: Dict, timeout: int = 30) -> Dict:
    resp = requests.post(url, data=data, timeout=timeout)
    body = {}
    try:
        body = resp.json()
    except ValueError:
        pass
    if resp.status_code >= 400 or "error" in body:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        parts = [str(err.get("message") or resp.text)]
        if err.get("code") is not None:
            parts.append(f"code={err.get('code')}")
        if err.get("error_subcode") is not None:
            parts.append(f"subcode={err.get('error_subcode')}")
        if err.get("error_user_msg"):
            parts.append(str(err.get("error_user_msg")))
        raise InstagramError("Graph API error: " + " | ".join(parts))
    return body


def fetch_username(account: Dict) -> Optional[str]:
    """Look up the real IG @username for an account via the Graph API.

    `GET /{ig-business-id}?fields=username` returns the handle tied to the
    business account, so the slide overlay can use the genuine username
    instead of a manually-typed value. Returns None on any error so callers
    can fall back gracefully (never raises).
    """
    ig_id = str(account.get("ig_business_id") or "")
    token = account.get("ig_access_token") or ""
    if not ig_id.isdigit() or _looks_like_placeholder(token):
        return None
    try:
        r = requests.get(
            f"{GRAPH}/{ig_id}",
            params={"fields": "username", "access_token": token},
            timeout=15,
        )
        data = r.json()
        username = data.get("username") if isinstance(data, dict) else None
        return str(username).strip() if username else None
    except Exception:
        return None


def _permalink(media_id: str, token: str) -> Optional[str]:
    try:
        r = requests.get(
            f"{GRAPH}/{media_id}",
            params={"fields": "permalink", "access_token": token},
            timeout=15,
        )
        return r.json().get("permalink")
    except Exception:
        return None


def publish(account: Dict, image_urls: List[str], caption: str) -> Dict:
    """Publish a post to `account`. Carousel if >1 image, else a single image.

    Returns {"ig_media_id", "permalink", "media_type"}.
    """
    _validate(account)
    if not image_urls:
        raise InstagramError("No image URLs to publish.")

    ig_id = account["ig_business_id"]
    token = account["ig_access_token"]

    if len(image_urls) == 1:
        created = _post(
            f"{GRAPH}/{ig_id}/media",
            {"image_url": image_urls[0], "caption": caption, "access_token": token},
        )
        published = _post(
            f"{GRAPH}/{ig_id}/media_publish",
            {"creation_id": created["id"], "access_token": token},
        )
        media_id = published["id"]
        return {"ig_media_id": media_id, "permalink": _permalink(media_id, token), "media_type": "image"}

    # --- carousel ---
    child_ids: List[str] = []
    for url in image_urls:
        child = _post(
            f"{GRAPH}/{ig_id}/media",
            {"image_url": url, "is_carousel_item": "true", "access_token": token},
        )
        child_ids.append(child["id"])

    container = _post(
        f"{GRAPH}/{ig_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": token,
        },
    )
    published = _post(
        f"{GRAPH}/{ig_id}/media_publish",
        {"creation_id": container["id"], "access_token": token},
    )
    media_id = published["id"]
    return {"ig_media_id": media_id, "permalink": _permalink(media_id, token), "media_type": "carousel"}
