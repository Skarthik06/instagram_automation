"""Intelligence stage — Marketing Strategist (07) + Carousel Planner (08).

Reasons ONLY over the validated Property Knowledge Model (never raw docs, never
unverified claims). Chooses the strongest angle for the available verified facts,
plans a carousel whose slides bind to REAL image assets, and writes a structured
caption. Fabricated facts / prices / urgency / returns are forbidden (Spec §12, §20).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.business.provider import LLMProvider

ANGLES = ["LOCATION_FIRST", "FAMILY_FIRST", "BUDGET_FIRST", "LIFESTYLE_FIRST",
          "AMENITY_FIRST", "CONNECTIVITY_FIRST", "SPACE_FIRST", "FLOOR_PLAN_FIRST",
          "BUILDER_TRUST"]

_SYSTEM = (
    "You are a senior real-estate performance marketer. You build Instagram carousel "
    "campaigns grounded ONLY in the verified facts you are given. You NEVER invent "
    "facts, prices, distances, approvals, urgency, scarcity, or guaranteed returns. "
    "If price is NOT_AVAILABLE you never mention a price. Respond with strict JSON only."
)


def _verified_facts(model: Dict[str, Any], enrich: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compact, LLM-ready projection of the validated model (Spec §28 — slice only)."""
    cfg = model.get("configuration") or []
    asset_types = {a["asset_type"] for a in model.get("media", [])
                   if a.get("usable") and a["asset_type"] != "unknown"}
    hotspots_ctx: List[Dict[str, Any]] = []
    if enrich:
        if enrich.get("map_asset"):
            asset_types.add("context_map")
        for h in (enrich.get("hotspots") or [])[:8]:
            hotspots_ctx.append({"name": h["name"], "category": h["category"],
                                 "approx_km": h["distance_km"]})
    return {
        "project_name": model["property"]["project_name"],
        "builder": model["property"]["builder"],
        "property_type": model["property"]["property_type"],
        "category": model["property"]["category"],
        "total_units": model["project"]["total_units"],
        "land_area": model["project"]["land_area"],
        "configuration": [{"bhk": c.get("bhk"), "area_sqft": c.get("area_sqft"),
                           "rooms": c.get("rooms", [])} for c in cfg],
        "location": {k: v for k, v in model["location"].items()
                     if v and v != "NOT_AVAILABLE" and k not in ("latitude", "longitude")},
        "amenities": model.get("amenities", []),
        "connectivity_from_brochure": [{"name": n["name"], "distance": n.get("distance")}
                                       for n in model.get("connectivity", [])],
        "nearby_hotspots_area_context": hotspots_ctx,
        "approvals": model.get("approvals", []),
        "views": model.get("views", []),
        "features": model.get("features", []),
        "price": model["pricing"]["price"],
        "contacts": model.get("contacts", []),
        "available_asset_types": sorted(asset_types),
    }


def _score_angles(f: Dict[str, Any]) -> List[str]:
    """Deterministic pre-ranking so the LLM chooses from the strongest, not a default."""
    s: Dict[str, int] = {a: 0 for a in ANGLES}
    if str(f.get("category")).lower() == "budget" or f.get("price") == "NOT_AVAILABLE":
        s["BUDGET_FIRST"] += 2
    if f.get("connectivity"):
        s["CONNECTIVITY_FIRST"] += len(f["connectivity"])
        s["LOCATION_FIRST"] += 1
    if any("floor_plan" in t for t in f.get("available_asset_types", [])):
        s["FLOOR_PLAN_FIRST"] += 2
    if f.get("amenities"):
        s["AMENITY_FIRST"] += min(3, len(f["amenities"]) // 3)
        s["FAMILY_FIRST"] += 1
    if f.get("views"):
        s["LIFESTYLE_FIRST"] += 1
    if f.get("configuration") and any(c.get("area_sqft") for c in f["configuration"]):
        s["SPACE_FIRST"] += 1
    if f.get("builder"):
        s["BUILDER_TRUST"] += 1
    return [a for a, _ in sorted(s.items(), key=lambda kv: kv[1], reverse=True) if s[a] > 0][:4] or ANGLES[:3]


def _prompt(facts: Dict[str, Any], brief: "CampaignBrief", forced_angle: Optional[str],
            candidate_angles: List[str], skeleton: List[str]) -> str:
    from app.business.campaign_brief import constraints_text
    angle_line = (f'Use EXACTLY this angle: {forced_angle}.' if forced_angle
                  else f'Pick the single strongest angle from: {candidate_angles}.')
    aud = brief.target_audience
    aud_line = ("Choose the most fitting audience from the verified data."
                if aud in ("ai_recommended", "custom", "") else f"Write specifically for: {aud}.")
    skeleton_line = " -> ".join(skeleton)
    return (
        f"VERIFIED FACTS (use ONLY these):\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Fact rules: `connectivity_from_brochure` distances are exact and developer-"
        "stated — quote them precisely. `nearby_hotspots_area_context` are APPROXIMATE "
        "neighbourhood context from maps (not the brochure) — reference generally, "
        "never as official brochure distances.\n\n"
        "CAMPAIGN BRIEF (obey ALL of these constraints):\n"
        f"{constraints_text(brief)}\n\n"
        f"{angle_line} {aud_line}\n"
        f"Build the carousel following this slide skeleton (one slide per slot, in order): "
        f"{skeleton_line}. Slide 1 must be a scroll-stopping hook. If 'context_map' is in "
        "available_asset_types, the 'map'/'location' slot should use image_asset_type "
        "'context_map'.\n"
        "Return JSON:\n"
        "{\n"
        '  "marketing": {"angle": "", "angle_rationale": "", "primary_audience": "",'
        ' "secondary_audiences": [string], "selling_points": [{"point": "", "based_on": "<verified fact>"}],'
        ' "hook_strategy": "", "cta": ""},\n'
        '  "carousel": {"strategy": "", "slides": [{"slide_number": int, "template":'
        ' "<slot from the skeleton>", "headline": "<=6 words", "subheadline": "<=14 words",'
        ' "facts": [string], "image_asset_type": "<one of available_asset_types or none>",'
        ' "badges": [string], "cta": ""}]},\n'
        '  "caption": {"hook": "", "body": "", "key_points": [string], "cta": "",'
        ' "hashtags": [14-20 lowercase, no #], "location_tags": [string], "keywords": [string]}\n'
        "}\n"
        "HASHTAGS for MAXIMUM REACH — balanced 14-20 mix (lowercase, no #, grounded in "
        "location facts): broad (realestate, propertyforsale), city, locality/landmark, "
        "type+config (2bhk, budgethomes), intent (sitevisit, newlaunch where true), and "
        "audience-fit tags. location_tags = real place names; keywords = SEO phrases.\n"
        f"LANGUAGE: write ALL slide headlines, subheadlines, facts, badges, cta and the "
        f"caption in '{brief.language}'. For a bilingual option (e.g. english_kannada) give "
        "the primary line in the first language and a short second-language line where "
        "natural. Hashtags stay latin/transliterated. Numbers and proper names keep their "
        "original form.\n"
        "Never state a price if price is NOT_AVAILABLE. Ground every concrete claim in "
        "the verified set."
    )


def _bind_assets(carousel: Dict[str, Any], model: Dict[str, Any],
                 enrich: Optional[Dict[str, Any]] = None) -> None:
    """Deterministically attach a REAL image URL to each slide by asset type (Spec §15).

    Property visuals come from real brochure images; the 'context_map' is the
    derived OSM map (clearly context, not the property)."""
    CONTEXT_TYPES = {"context_photo", "context_map"}
    CONTEXT_TMPL = {"location", "map", "connectivity", "metro", "schools", "hospitals",
                    "shopping", "transport", "nearby", "hotspots"}
    usable = [a for a in model.get("media", []) if a.get("usable") and a.get("cdn_url")
              and a.get("asset_type") not in ("unknown", "logo", "builder_logo", "document_scan")]
    usable.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    if enrich and enrich.get("map_asset"):
        usable.append(enrich["map_asset"])

    # Two pools: REAL property images vs FETCHED/derived context images. Property
    # slides only ever show real property images; context slides can show the
    # matching high-res context photo (metro/mall/school) or the OSM map (Spec §15).
    prop_pool = [a for a in usable if a["asset_type"] not in CONTEXT_TYPES]
    ctx_pool = [a for a in usable if a["asset_type"] in CONTEXT_TYPES]
    used: set = set()

    def _take(pool: List[Dict[str, Any]], want: Optional[str] = None):
        if want and want != "none":
            for a in pool:
                if a["asset_type"] == want and a["storage_ref"] not in used:
                    return a
        for a in pool:
            if a["storage_ref"] not in used:
                return a
        return pool[0] if pool else None

    for sl in carousel.get("slides", []):
        want = sl.get("image_asset_type")
        is_ctx_slot = sl.get("template") in CONTEXT_TMPL or want in CONTEXT_TYPES
        asset = _take(ctx_pool, want) if is_ctx_slot else _take(prop_pool, want)
        if not asset:                                   # fall back across pools
            asset = _take(prop_pool) if is_ctx_slot else _take(ctx_pool)
        if asset:
            used.add(asset["storage_ref"])
            sl["image_is_context_bg"] = asset["asset_type"] in CONTEXT_TYPES
        sl["image_ref"] = asset["cdn_url"] if asset else None
        sl["image_source"] = asset["storage_ref"] if asset else None
        sl["image_attribution"] = (asset or {}).get("attribution", "")


_SLOT_HEADLINE = {
    "hero": "Discover your next home", "overview": "Project overview",
    "project_overview": "Project overview", "price_value": "Value that adds up",
    "floor_plan": "Smart, efficient layout", "amenities": "Amenities for everyday living",
    "living_spaces": "Bright, open living", "bedrooms": "Restful bedrooms",
    "kitchen_bath": "Modern kitchen & baths", "location": "A prime address",
    "connectivity": "Well connected", "schools_hospitals": "Schools & care nearby",
    "shopping_lifestyle": "Shopping & lifestyle close by", "builder_approvals": "Trusted, approved",
    "builder_trust": "Built on trust", "why_invest": "A smart place to invest",
    "feature": "Another highlight", "cta": "Book a site visit",
}


def _reconcile_slides(slides: List[Dict[str, Any]], slots: List[Dict[str, Any]],
                      facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Make the slide list exactly match the slot plan so every image slot is filled.
    LLM copy is kept where present (by index); missing slots get a grounded fallback."""
    out: List[Dict[str, Any]] = []
    for i, spec in enumerate(slots):
        if i < len(slides) and isinstance(slides[i], dict):
            s = dict(slides[i])
        else:
            s = {"headline": _SLOT_HEADLINE.get(spec.get("slot"), "Highlight"),
                 "subheadline": "", "facts": []}
        s.setdefault("template", spec.get("slot"))
        out.append(s)
    return out


def build_campaign(model: Dict[str, Any], provider: LLMProvider, brief: "CampaignBrief",
                   *, enrich: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from app.business.campaign_brief import violates_claim_policy
    facts = _verified_facts(model, enrich)
    candidates = _score_angles(facts)
    # User-selected angle wins; otherwise the LLM picks from the strongest candidates.
    forced_angle = None
    if brief.content_angle not in ("ai_recommended", "custom", "balanced", ""):
        forced_angle = brief.content_angle
    angle_for_skeleton = forced_angle or (candidates[0] if candidates else "balanced")

    # Carousel Structure Agent (deterministic): pick a fixed 10-slide structure and
    # size it so EVERY real PDF image gets its own slot (none missed, min 10 slides).
    from app.business import carousel_structure as cs
    structure_name = cs.resolve_structure(brief.carousel_type, angle_for_skeleton)
    real_count = len(cs.real_images(model))             # ALL brochure images (none missed)
    min_slides = max(10, brief.slide_count)             # 10 minimum; grows past it below
    slots = cs.build_slots(structure_name, real_count=real_count, min_slides=min_slides,
                           enrichment=list(getattr(brief, "data_enrichment", []) or []))
    skeleton = [s["slot"] for s in slots]

    out = provider.structured_output(
        system=_SYSTEM,
        user=_prompt(facts, brief, forced_angle, candidates, skeleton),
        max_tokens=min(8000, 900 + len(slots) * 360),
    )
    marketing = out.get("marketing", {})
    carousel = out.get("carousel", {"slides": []})
    caption = out.get("caption", {})

    # Enforce brief controls deterministically (the LLM executes, the brief decides).
    if forced_angle:
        marketing["angle"] = forced_angle
    if brief.cta_text:
        marketing["cta"] = brief.cta_text
        caption["cta"] = brief.cta_text

    # Align slide COUNT to the slot plan so every image slot exists, then bind images
    # deterministically per slot (copy + image now come from the same slot -> they match).
    carousel["slides"] = _reconcile_slides(carousel.get("slides", []), slots, facts)
    cs.bind_images(carousel["slides"], slots, model, enrich,
                   image_policy=getattr(brief, "image_policy", "real_images_plus_design"))

    # STRICT claim-policy guard: flag any banned hype in the generated copy.
    copy_blob = " ".join([caption.get("hook", ""), caption.get("body", ""),
                          " ".join(s.get("headline", "") + " " + s.get("subheadline", "")
                                   for s in carousel.get("slides", []))])
    claim_violations = violates_claim_policy(brief, copy_blob)

    return {
        "goal": brief.goal,
        "brief": brief.model_dump(),
        "candidate_angles": candidates,
        "marketing": marketing,
        "carousel": carousel,
        "caption": caption,
        "claim_violations": claim_violations,
        "_trace": {"agent": "07/08-marketing+carousel", "angle": marketing.get("angle"),
                   "audience": brief.target_audience, "carousel_type": brief.carousel_type,
                   "slides": len(carousel.get("slides", [])),
                   "slides_with_image": sum(1 for s in carousel.get("slides", []) if s.get("image_ref")),
                   "claim_violations": len(claim_violations)},
    }
