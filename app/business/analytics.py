"""M7 — Instagram Insights (analytics) via the Graph API.

Pulls per-media insights for a published campaign (reach, saves, likes, comments,
shares, total interactions, views) using the same account token as the publisher.
Metrics availability varies by media type / API version, so we degrade gracefully
and store whatever the API returns. Requires a REAL published media id.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from app.services.instagram import GRAPH, InstagramError

# Metrics we try for a carousel/post; the API is asked for these and returns the
# subset it supports for that media.
_MEDIA_METRICS = ["reach", "saved", "likes", "comments", "shares",
                  "total_interactions", "views"]


def fetch_media_insights(account: Dict[str, Any], media_id: str) -> Dict[str, Any]:
    token = account.get("ig_access_token") or ""
    if not media_id or not token:
        raise InstagramError("Missing media id or account token for insights.")
    metrics = ",".join(_MEDIA_METRICS)
    try:
        r = requests.get(f"{GRAPH}/{media_id}/insights",
                         params={"metric": metrics, "access_token": token}, timeout=20)
        body = r.json()
    except Exception as exc:  # noqa: BLE001
        raise InstagramError(f"Insights request failed: {exc}") from exc
    if isinstance(body, dict) and body.get("error"):
        # Retry with a minimal, universally-supported set before giving up.
        try:
            r = requests.get(f"{GRAPH}/{media_id}/insights",
                             params={"metric": "reach,saved", "access_token": token}, timeout=20)
            body = r.json()
        except Exception as exc:  # noqa: BLE001
            raise InstagramError(f"Insights request failed: {exc}") from exc
        if isinstance(body, dict) and body.get("error"):
            raise InstagramError("Graph insights error: " + str(body["error"].get("message")))
    out: Dict[str, Any] = {}
    for item in (body.get("data") or []):
        name = item.get("name")
        values = item.get("values") or [{}]
        out[name] = values[0].get("value")
    return out


def score_campaign(metrics: Dict[str, Any]) -> float:
    """Simple engagement score for ranking campaigns (Spec §31/§37 — analytics
    first, no RL). Weighted toward saves/shares (intent) over passive reach."""
    def n(k):
        try:
            return float(metrics.get(k) or 0)
        except (TypeError, ValueError):
            return 0.0
    reach = max(1.0, n("reach"))
    interactions = n("total_interactions") or (n("likes") + n("comments") + n("shares") + n("saved"))
    engagement_rate = interactions / reach
    intent = 2.0 * n("saved") + 1.5 * n("shares")
    return round(engagement_rate * 100 + intent, 2)


def compare(campaigns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank campaigns by score; each item {campaign_id, angle, score, metrics}."""
    ranked = sorted(campaigns, key=lambda c: c.get("score", 0), reverse=True)
    return ranked
