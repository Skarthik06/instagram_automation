"""Orchestrator (Agent 00) — run one document end-to-end and emit the IG contract.

Enforces the stage order and collects per-stage traces + total LLM cost
(observability, Spec §4). Ends at the integration contract (Spec §26); the existing
Instagram engine consumes it — this platform never publishes directly.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict

from app import settings
from app.business import enrich, knowledge, marketing, rendering
from app.business.extraction import extract_document
from app.business.provider import Usage, get_provider

_OUT = settings.IMAGES_DIR / "business"
_CDN = "/cdn/business"


def _caption_text(cap: Dict[str, Any]) -> str:
    from app.business.textpolish import polish, polish_caption, bold
    parts = []
    if cap.get("hook"):
        parts.append(bold(polish(cap["hook"])))          # bold, grammar-fixed hook line
    if cap.get("body"):
        parts.append(polish_caption(cap["body"]))
    if cap.get("key_points"):
        parts.append("\n".join(f"• {polish(p)}" for p in cap["key_points"]))
    if cap.get("cta"):
        parts.append(polish(cap["cta"]))
    tags = " ".join("#" + re.sub(r"[^a-z0-9]", "", t.lower().lstrip("#"))
                    for t in cap.get("hashtags", []) if t)
    if tags:
        parts.append(tags)
    return "\n\n".join(parts).strip()


def extract_property(pdf_path: str | Path) -> Dict[str, Any]:
    """STAGE A (run once per document): extract -> knowledge -> evidence -> validate
    -> enrich. Returns the validated Property Knowledge Model + verdict + usage. This
    is saved and reused across many campaigns without re-parsing (Spec §36, §40)."""
    t0 = time.time()
    usage = Usage()
    provider = get_provider(usage)
    _OUT.mkdir(parents=True, exist_ok=True)

    bundle = extract_document(pdf_path, out_dir=_OUT, cdn_prefix=_CDN)
    entities = knowledge.extract_entities(bundle, provider)
    assets = knowledge.classify_images(bundle, provider)
    model = knowledge.validate(entities, bundle, assets)

    location_intel = enrich.enrich_location(model, out_dir=_OUT, cdn_prefix=_CDN)
    if location_intel.get("map_asset"):
        model.setdefault("media", []).append(location_intel["map_asset"])
    for photo in location_intel.get("context_photos", []):
        model.setdefault("media", []).append(photo)   # real high-res context images
    model["location_intelligence"] = {k: v for k, v in location_intel.items() if k != "_trace"}

    return {
        "document": bundle.document,
        "knowledge_model": {k: v for k, v in model.items() if not k.startswith("_")},
        "verdict": model.get("_verdict"),
        "traces": [t for t in (bundle.trace, entities.get("_trace"), model.get("_trace"),
                               location_intel.get("_trace")) if t],
        "usage": usage.as_dict(),
        "duration_ms": int((time.time() - t0) * 1000),
    }


def generate_campaign(model: Dict[str, Any], brief, *, render: bool = True,
                      brand: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """STAGE B (run per campaign): Brief + saved Property Knowledge -> marketing ->
    carousel -> render -> contract. No re-extraction (fast + cheap + consistent)."""
    t0 = time.time()
    usage = Usage()
    provider = get_provider(usage)
    location_intel = model.get("location_intelligence") or {}

    campaign = marketing.build_campaign(model, provider, brief, enrich=location_intel)

    render_result = (rendering.render_carousel(campaign, model, out_dir=_OUT, cdn_prefix=_CDN, brand=brand)
                     if render else {"rendered": False, "images": [], "count": 0})

    contract = {
        "campaign_id": f"{model['property']['id']}-{brief.goal}",
        "property_id": model["property"]["id"],
        "carousel": {"slides": campaign["carousel"].get("slides", []),
                     "images": render_result.get("images", [])},
        "caption": _caption_text(campaign.get("caption", {})),
        "hashtags": campaign.get("caption", {}).get("hashtags", []),
        "cta": campaign.get("marketing", {}).get("cta", ""),
        "metadata": {"goal": brief.goal, "audience": brief.target_audience,
                     "angle": campaign.get("marketing", {}).get("angle"),
                     "carousel_type": brief.carousel_type, "brief_version": brief.campaign_version},
    }
    return {
        "brief": brief.model_dump(),
        "marketing": campaign.get("marketing"),
        "carousel": campaign.get("carousel"),
        "caption": campaign.get("caption"),
        "claim_violations": campaign.get("claim_violations", []),
        "render": render_result,
        "contract": contract,
        "traces": [t for t in (campaign.get("_trace"), render_result.get("_trace")) if t],
        "usage": usage.as_dict(),
        "duration_ms": int((time.time() - t0) * 1000),
    }


def run(pdf_path: str | Path, *, goal: str = "site_visit", slides: int = 6,
        render: bool = True, brief=None) -> Dict[str, Any]:
    """Backward-compatible one-shot: extract + one campaign. Accepts an optional
    CampaignBrief; otherwise builds a default brief from goal/slides."""
    from app.business.campaign_brief import CampaignBrief
    if brief is None:
        brief = CampaignBrief(goal=goal, slide_count=slides)
    extracted = extract_property(pdf_path)
    model = extracted["knowledge_model"]
    campaign = generate_campaign(model, brief, render=render)
    merged = {**extracted, **{k: v for k, v in campaign.items() if k != "traces"}}
    merged["traces"] = extracted["traces"] + campaign["traces"]
    merged["usage"] = extracted["usage"]  # combined view is approximate; both cached anyway
    merged["duration_ms"] = extracted["duration_ms"] + campaign["duration_ms"]
    merged["knowledge_model"] = model
    merged["verdict"] = extracted["verdict"]
    return merged
