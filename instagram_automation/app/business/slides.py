"""Per-slide operations (M3, Spec §19/§21) — edit, lock, regenerate copy/image.

Regeneration is grounded ONLY in the validated Property Knowledge and the Campaign
Brief; it never invents facts and never touches a locked slide. Copy is AI-editable;
factual values remain locked (fact-lock, Spec §17).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.business import marketing
from app.business.campaign_brief import CampaignBrief, constraints_text
from app.business.provider import LLMProvider

_SYS = ("You rewrite ONE Instagram real-estate carousel slide's copy, grounded ONLY "
        "in the verified facts provided. Never invent facts, numbers, or claims. "
        "Return strict JSON only.")


def _brief_from(d: Dict[str, Any]) -> CampaignBrief:
    fields = getattr(CampaignBrief, "model_fields", {})
    return CampaignBrief(**{k: v for k, v in (d or {}).items() if k in fields})


def _regen_copy(model: Dict[str, Any], brief: CampaignBrief, slide: Dict[str, Any],
                provider: LLMProvider) -> Dict[str, Any]:
    facts = marketing._verified_facts(model, model.get("location_intelligence"))
    prompt = (
        f"VERIFIED FACTS (use ONLY these):\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"CAMPAIGN BRIEF:\n{constraints_text(brief)}\n\n"
        f"Rewrite this ONE slide (template = {slide.get('template')}). Keep it on-message "
        f"for the audience and angle. Return JSON: "
        '{"headline": "<=6 words", "subheadline": "<=14 words", "facts": [string], "cta": ""}. '
        "Only verified facts; never state a price if price is NOT_AVAILABLE."
    )
    out = provider.structured_output(system=_SYS, user=prompt, max_tokens=500)
    for k in ("headline", "subheadline", "cta"):
        if out.get(k):
            slide[k] = out[k]
    if isinstance(out.get("facts"), list):
        slide["facts"] = out["facts"][:5]
    return slide


def _regen_image(model: Dict[str, Any], slide: Dict[str, Any]) -> Dict[str, Any]:
    """Cycle the slide to a different REAL asset (never a fabricated visual)."""
    want = slide.get("image_asset_type")
    usable = [a for a in model.get("media", []) if a.get("usable")]
    same = [a for a in usable if a["asset_type"] == want] or usable
    cur = slide.get("image_source")
    candidates = [a for a in same if a.get("storage_ref") != cur] or same
    if candidates:
        a = candidates[0]
        slide["image_ref"] = a["cdn_url"]
        slide["image_source"] = a["storage_ref"]
        slide["image_attribution"] = a.get("attribution", "")
        slide["image_asset_type"] = a["asset_type"]
    return slide


def regenerate_slide(model: Dict[str, Any], brief_dict: Dict[str, Any],
                     carousel: Dict[str, Any], index: int, mode: str,
                     provider: LLMProvider) -> Dict[str, Any]:
    slides: List[Dict[str, Any]] = carousel.get("slides", [])
    if index < 0 or index >= len(slides):
        raise IndexError("slide index out of range")
    slide = slides[index]
    if slide.get("locked"):
        return slide  # locked slides are never altered by regeneration (Spec §21)
    brief = _brief_from(brief_dict)
    if mode in ("copy", "entire", "layout"):
        slide = _regen_copy(model, brief, slide, provider)
    if mode in ("image", "entire"):
        slide = _regen_image(model, slide)
    slides[index] = slide
    return slide


def edit_slide(carousel: Dict[str, Any], index: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Manual human edit of a slide's copy (fact values stay whatever the user typed)."""
    slides = carousel.get("slides", [])
    if index < 0 or index >= len(slides):
        raise IndexError("slide index out of range")
    allowed = {"headline", "subheadline", "facts", "cta", "badges", "template",
               "image_asset_type", "contacts", "footer", "brandname", "locality"}
    for k, v in (fields or {}).items():
        if k in allowed and v is not None:
            slides[index][k] = v
    return slides[index]


def set_lock(carousel: Dict[str, Any], index: int, locked: bool) -> Dict[str, Any]:
    slides = carousel.get("slides", [])
    if index < 0 or index >= len(slides):
        raise IndexError("slide index out of range")
    slides[index]["locked"] = locked
    return slides[index]


def reorder(carousel: Dict[str, Any], order: List[int]) -> List[Dict[str, Any]]:
    slides = carousel.get("slides", [])
    if sorted(order) != list(range(len(slides))):
        raise ValueError("reorder must be a permutation of all slide indices")
    carousel["slides"] = [slides[i] for i in order]
    for n, s in enumerate(carousel["slides"], 1):
        s["slide_number"] = n
    return carousel["slides"]
