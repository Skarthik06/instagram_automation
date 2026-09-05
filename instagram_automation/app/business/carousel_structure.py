"""Carousel Structure Agent (governed by business/agents/carousel-planner.agents.md).

Defines FIXED 10-slide posting structures and binds a REAL image to every slot
DETERMINISTICALLY (charter §2: "IG dimension/slot logic is deterministic").

The rule the owner asked for:
  1. Prioritise the PDF's OWN images first, matched to the slot by asset type
     (hero -> exterior, floorplan -> floor plan, bedrooms -> bedroom, ...).
  2. Property slots NEVER show a fetched/context photo. If the brochure runs out
     of a matching image we REUSE a real property image (cycle) — we never drop a
     hospital/supermarket/stock photo onto a property slide (that was the bug).
  3. Context photos (metro/school/hospital/mall) and the OSM map appear ONLY on the
     location / connectivity / nearby slots, matched to that slot's subject.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Real images that come from the source PDF/brochure (Agent 03 classification).
PROPERTY_TYPES = {
    "building_exterior", "building_interior", "living_room", "bedroom", "kitchen",
    "bathroom", "balcony", "amenity", "kids_area", "sports", "parking", "landscape",
    "floor_plan", "site_plan", "cluster_plan", "location_map", "architectural_render",
}
CONTEXT_TYPES = {"context_photo", "context_map"}
_MAP_TYPES = ("context_map", "location_map")

# --- The three fixed 10-slide structures (owner-selected; Investor/Value leads) ---
# Each slot: slot(name) · role(property|context|cta) · assets(ranked real types) ·
# subject(optional keyword to match a context photo's category).
_P = "property"; _C = "context"; _X = "cta"

STRUCTURES: Dict[str, List[Dict[str, Any]]] = {
    # Option 3 — Investor / Value (leads with value, growth, builder trust, approvals)
    "investor_value": [
        {"slot": "hero", "role": _P, "assets": ["building_exterior", "architectural_render", "building_interior", "landscape"]},
        {"slot": "project_overview", "role": _P, "assets": ["building_exterior", "architectural_render", "site_plan", "landscape"]},
        {"slot": "price_value", "role": _P, "assets": ["building_exterior", "architectural_render", "building_interior", "living_room"]},
        {"slot": "floor_plan", "role": _P, "assets": ["floor_plan", "site_plan", "cluster_plan"]},
        {"slot": "amenities", "role": _P, "assets": ["amenity", "sports", "kids_area", "parking", "landscape"]},
        {"slot": "location", "role": _C, "assets": ["context_map", "location_map"]},
        {"slot": "connectivity", "role": _C, "assets": ["context_photo"], "subject": "metro"},
        {"slot": "builder_approvals", "role": _P, "assets": ["building_exterior", "architectural_render", "building_interior"]},
        {"slot": "why_invest", "role": _C, "assets": ["context_photo", "context_map"], "subject": "mall"},
        {"slot": "cta", "role": _X, "assets": ["building_exterior", "architectural_render", "building_interior"]},
    ],
    # Option 1 — Property Tour (maximises real PDF images)
    "property_tour": [
        {"slot": "hero", "role": _P, "assets": ["building_exterior", "architectural_render"]},
        {"slot": "overview", "role": _P, "assets": ["building_exterior", "architectural_render", "site_plan", "landscape"]},
        {"slot": "living_spaces", "role": _P, "assets": ["living_room", "building_interior"]},
        {"slot": "bedrooms", "role": _P, "assets": ["bedroom", "balcony", "building_interior"]},
        {"slot": "kitchen_bath", "role": _P, "assets": ["kitchen", "bathroom"]},
        {"slot": "amenities", "role": _P, "assets": ["amenity", "sports", "kids_area", "parking"]},
        {"slot": "floor_plan", "role": _P, "assets": ["floor_plan", "site_plan", "cluster_plan"]},
        {"slot": "location", "role": _C, "assets": ["context_map", "location_map"]},
        {"slot": "connectivity", "role": _C, "assets": ["context_photo"], "subject": "metro"},
        {"slot": "cta", "role": _X, "assets": ["building_exterior", "architectural_render", "building_interior"]},
    ],
    # Option 2 — Location-First (neighbourhood is the selling point)
    "location_first": [
        {"slot": "hero", "role": _P, "assets": ["building_exterior", "architectural_render"]},
        {"slot": "overview", "role": _P, "assets": ["building_exterior", "architectural_render", "site_plan"]},
        {"slot": "amenities", "role": _P, "assets": ["amenity", "sports", "kids_area", "parking"]},
        {"slot": "floor_plan", "role": _P, "assets": ["floor_plan", "site_plan", "cluster_plan"]},
        {"slot": "location", "role": _C, "assets": ["context_map", "location_map"]},
        {"slot": "connectivity", "role": _C, "assets": ["context_photo"], "subject": "metro"},
        {"slot": "schools_hospitals", "role": _C, "assets": ["context_photo"], "subject": "hospital"},
        {"slot": "shopping_lifestyle", "role": _C, "assets": ["context_photo"], "subject": "mall"},
        {"slot": "builder_trust", "role": _P, "assets": ["building_exterior", "architectural_render", "building_interior"]},
        {"slot": "cta", "role": _X, "assets": ["building_exterior", "architectural_render"]},
    ],
}

# Which structure a carousel_type / angle maps to.
_CTYPE_TO_STRUCTURE = {
    "investment": "investor_value", "price_value": "investor_value", "builder_trust": "investor_value",
    "property_showcase": "property_tour", "property_launch": "property_tour",
    "property_discovery": "property_tour", "project_overview": "property_tour",
    "family_lifestyle": "property_tour", "amenities_showcase": "property_tour",
    "floor_plan_breakdown": "property_tour",
    "location_guide": "location_first", "connectivity": "location_first", "educational": "location_first",
}
_ANGLE_TO_STRUCTURE = {
    "investment_first": "investor_value", "price_first": "investor_value", "value_first": "investor_value",
    "builder_trust": "investor_value", "location_first": "location_first",
    "connectivity_first": "location_first", "floor_plan_first": "property_tour",
    "family_first": "property_tour", "amenities_first": "property_tour", "space_first": "property_tour",
}

DEFAULT_STRUCTURE = "investor_value"   # owner chose Option 3 to lead


def resolve_structure(carousel_type: str, angle: str) -> str:
    return (_CTYPE_TO_STRUCTURE.get(carousel_type)
            or _ANGLE_TO_STRUCTURE.get(angle)
            or DEFAULT_STRUCTURE)


_MAX_SLIDES = 10                            # strict 10-slide post — all content packed into one carousel
_GALLERY_ASSETS = ["building_interior", "living_room", "bedroom", "kitchen", "balcony",
                   "amenity", "sports", "kids_area", "parking", "landscape",
                   "architectural_render", "building_exterior"]


# Data-enrichment selections (the brief's `data_enrichment`) -> extra context slides.
# Selecting "Nearby Schools" etc. ADDS a dedicated slide with the fetched photo, so
# the user's choices actually appear in the carousel (it grows past 10 as needed).
_ENRICHMENT_SLOTS: Dict[str, Dict[str, Any]] = {
    "map_location": {"slot": "location", "role": _C, "assets": ["context_map", "location_map"]},
    "nearby_schools": {"slot": "schools", "role": _C, "assets": ["context_photo"], "subject": "school"},
    "nearby_hospitals": {"slot": "hospitals", "role": _C, "assets": ["context_photo"], "subject": "hospital"},
    "nearby_malls": {"slot": "shopping", "role": _C, "assets": ["context_photo"], "subject": "mall"},
    "metro_transport": {"slot": "connectivity", "role": _C, "assets": ["context_photo"], "subject": "metro"},
    "locality_info": {"slot": "locality", "role": _C, "assets": ["context_map", "context_photo"], "subject": "park"},
    "market_info": {"slot": "market", "role": _C, "assets": ["context_map", "context_photo"]},
}


def _feature_slot() -> Dict[str, Any]:
    return {"slot": "feature", "role": _P, "assets": list(_GALLERY_ASSETS)}


# When the plan must fit a strict cap, which slots survive (lower = keep first).
# The user's SELECTED enrichments are priority 1, so they always make the cut.
_SELECT_PRIORITY = {
    "hero": 0,
    "location": 1, "connectivity": 1, "schools": 1, "hospitals": 1, "shopping": 1, "metro": 1,
    "overview": 2, "project_overview": 2, "floor_plan": 2, "amenities": 2, "price_value": 2,
    "market": 2, "locality": 2,
    "living_spaces": 3, "bedrooms": 3, "kitchen_bath": 3, "builder_approvals": 3,
    "builder_trust": 3, "why_invest": 3, "feature": 4,
}
# Narrative reading order once the survivors are chosen (property first, context, CTA last).
_ORDER = {
    "hero": 0, "overview": 1, "project_overview": 1, "price_value": 2, "living_spaces": 3,
    "bedrooms": 4, "kitchen_bath": 5, "amenities": 6, "floor_plan": 7, "builder_approvals": 8,
    "builder_trust": 8, "feature": 12, "location": 20, "connectivity": 21, "schools": 22,
    "hospitals": 23, "shopping": 24, "market": 25, "locality": 26, "why_invest": 27, "cta": 99,
}


def build_slots(structure: str, real_count: int = 0, min_slides: int = 10,
                enrichment: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Compose the slide plan, capped at `_MAX_SLIDES` (strict 10):
      - hero first, CTA last (always kept),
      - every SELECTED data-enrichment (schools/hospitals/malls/metro/location) is kept
        by priority — so the user's choices are analysed INTO the 10, not trimmed off,
      - remaining room filled by the most important property slots,
      - survivors ordered narratively (property -> context -> CTA)."""
    cap = min(max(min_slides, 3), _MAX_SLIDES)
    base = [dict(s) for s in STRUCTURES.get(structure, STRUCTURES[DEFAULT_STRUCTURE])]
    cta = next((s for s in base if s["role"] == _X), base[-1])
    hero = base[0]

    # candidate pool = base body (minus hero/cta) + a slide per selected enrichment
    pool, seen = [], {hero["slot"], cta.get("slot")}
    for s in base:
        if s is hero or s.get("role") == _X or s["slot"] in seen:
            continue
        pool.append(dict(s)); seen.add(s["slot"])
    for key in (enrichment or []):
        spec = _ENRICHMENT_SLOTS.get(key)
        if spec and spec["slot"] not in seen:
            pool.append(dict(spec)); seen.add(spec["slot"])
    # add gallery slots for extra real images (lowest priority — fill only if room)
    for _ in range(max(0, real_count - sum(1 for s in pool if s.get("role") == _P))):
        pool.append(_feature_slot())

    # keep the highest-priority (cap - 2) survivors (hero + cta take 2 slots)
    pool.sort(key=lambda s: (_SELECT_PRIORITY.get(s["slot"], 3),))
    chosen = pool[: max(0, cap - 2)]
    # order the survivors narratively, then bookend with hero + cta
    chosen.sort(key=lambda s: _ORDER.get(s["slot"], 15))
    return [hero, *chosen, cta][:cap]


_EXCLUDE = ("unknown", "logo", "builder_logo", "document_scan")


def real_images(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """EVERY real PDF image (none missed) — logos/scans excluded. The small-size
    `usable` flag is intentionally ignored: the owner wants all brochure images used,
    and slides render at 2160px so even a small crop scales up fine."""
    seen, out = set(), []
    for a in model.get("media", []):
        ref = a.get("storage_ref") or a.get("cdn_url")
        if not a.get("cdn_url") or ref in seen:
            continue
        if a.get("asset_type") in PROPERTY_TYPES:
            seen.add(ref); out.append(a)
    out.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return out


def _usable_media(model: Dict[str, Any], enrich: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    media = list(real_images(model))
    media += [a for a in model.get("media", []) if a.get("usable") and a.get("cdn_url")
              and a.get("asset_type") in CONTEXT_TYPES]
    if enrich and enrich.get("map_asset"):
        media.append(enrich["map_asset"])
    return media


# Subject detection: map words in a slide's headline/slot to a fetchable photo subject.
# This is what makes the IMAGE follow the TEXT — a "Nearby Schools" headline forces a
# school photo, "Healthcare Proximity" a hospital, etc. (enforced image↔text alignment).
_SUBJECT_KEYWORDS = [
    (("school", "education", "learning", "college", "academy"), "school"),
    (("hospital", "healthcare", "medical", "clinic", "health"), "hospital"),
    (("shopping", "mall", "retail", "store", "supermarket", "grocery", "groceries",
      "daily needs", "market", "convenience", "essential", "provisions"), "mall"),
    (("metro", "transit", "connectivity", "transport", "station", "railway", "commute",
      "roads", "access", "connected", "well-connected"), "metro"),
    (("park", "garden", "green", "jogging"), "park"),
    (("gym", "fitness"), "gym"),
    (("restaurant", "dining", "cafe", "eatery"), "restaurant"),
]
# Fetchable context subjects -> imagesearch query phrase.
_SUBJECT_QUERY = {"school": "school building", "hospital": "hospital building",
                  "mall": "shopping mall", "metro": "metro station", "park": "city park",
                  "gym": "fitness gym", "restaurant": "restaurant"}

# LIFESTYLE subjects — used ONLY under the "AI Recommended" strategy to fill property
# feature slots that have no real PDF image with a relevant AI-fetched image (never
# faking THIS property's specifics — clearly illustrative lifestyle/context imagery).
_LIFESTYLE_KEYWORDS = [
    (("security", "safety", "gated", "cctv", "secure", "surveillance"), "gated community security"),
    (("clubhouse", "recreation", "lounge", "community hall"), "clubhouse interior"),
    (("pool", "swimming"), "swimming pool"),
    (("parking", "car park", "covered parking"), "covered car parking"),
    (("garden", "landscape", "green", "play area", "jogging", "open space"), "landscaped garden"),
    (("loan", "finance", "value", "investment", "price", "offer", "booking"), "house keys handover"),
    (("power", "water", "utility", "backup", "sustainab", "rainwater", "solar"), "modern apartment building"),
    (("interior", "fitting", "furnish", "decor", "modern", "spacious", "elegant", "premium"), "modern apartment interior"),
    (("family", "comfort", "lifestyle", "living", "home"), "happy family home"),
]


def _detect_subject(text: str) -> Optional[str]:
    low = (text or "").lower()
    for keys, subj in _SUBJECT_KEYWORDS:
        if any(k in low for k in keys):
            return subj
    return None


def _detect_lifestyle(text: str) -> Optional[str]:
    low = (text or "").lower()
    for keys, subj in _LIFESTYLE_KEYWORDS:
        if any(k in low for k in keys):
            return subj
    return None


def bind_images(slides: List[Dict[str, Any]], slots: List[Dict[str, Any]],
                model: Dict[str, Any], enrich: Optional[Dict[str, Any]] = None,
                image_policy: str = "real_images_plus_design") -> None:
    """Attach an image to each slide so it MATCHES the slide's text (enforced):
      - property content -> real PDF image (by type),
      - a context subject in the headline (schools/hospital/mall/metro/park...) -> a
        photo of THAT subject: an already-fetched one, else AI-fetched on demand,
      - maps only on location slots.
    `image_policy` controls fetching: real_images_only never fetches (reuses real);
    real_images_plus_design / ai_recommended fetch matching photos; creative_backgrounds
    leaves a designed background where no real image fits. Mutates each slide in place."""
    def _area(a):
        try:
            w, h = str(a.get("resolution", "")).lower().split("x")
            return int(w) * int(h)
        except Exception:  # noqa: BLE001
            return 0

    def _min_side(a):
        try:
            w, h = str(a.get("resolution", "")).lower().split("x")
            return min(int(w), int(h))
        except Exception:  # noqa: BLE001
            return 9999

    media = _usable_media(model, enrich)
    # Sharpest images first -> the biggest, cleanest images land on the prominent
    # early slots (hero, overview); small crops fall to later gallery slots.
    # Maps are EXCLUDED from the generic property pool so a map never lands on a
    # bedroom/kitchen slide — maps go only to location/map slots (see `maps` below).
    real = sorted([a for a in media if a.get("asset_type") in PROPERTY_TYPES
                   and a.get("asset_type") != "location_map"],
                  key=lambda x: (_area(x), x.get("confidence", 0)), reverse=True)
    ctx_photos = [a for a in media if a.get("asset_type") == "context_photo"]
    maps = [a for a in media if a.get("asset_type") in _MAP_TYPES]
    used: set = set()
    cyc = [0]

    def _ref(a):
        return a.get("storage_ref") or a.get("cdn_url")

    def take_real(prefs: List[str], allow_reuse: bool = True):
        for t in prefs:                                  # 1) unused image of a wanted type
            for a in real:
                if a.get("asset_type") == t and _ref(a) not in used:
                    used.add(_ref(a)); return a
        for a in real:                                   # 2) any unused real image
            if _ref(a) not in used:
                used.add(_ref(a)); return a
        if not allow_reuse:                              # exhausted -> design background (None)
            return None
        for t in prefs:                                  # 3) reuse a wanted-type real image
            for a in real:
                if a.get("asset_type") == t:
                    return a
        if real:                                         # 4) reuse round-robin (never context)
            a = real[cyc[0] % len(real)]; cyc[0] += 1; return a
        return None

    def take_ctx(subject: Optional[str]):
        if subject:
            # A subject ONLY ever matches a photo of that exact category — never a
            # random context photo (that was the hospital-on-features bug).
            for a in ctx_photos:
                cat = (a.get("category") or a.get("subject") or "").lower()
                if subject in cat and _ref(a) not in used:
                    used.add(_ref(a)); return a
            for a in ctx_photos:                         # reuse a matching one
                cat = (a.get("category") or a.get("subject") or "").lower()
                if subject in cat:
                    return a
            return None                                  # no match -> caller fetches it
        for a in ctx_photos:                             # subject=None -> any unused
            if _ref(a) not in used:
                used.add(_ref(a)); return a
        return ctx_photos[0] if ctx_photos else None

    def take_map():
        for a in maps:
            if _ref(a) not in used:
                used.add(_ref(a)); return a
        return maps[0] if maps else None

    city = (model.get("location") or {}).get("city") or (model.get("location") or {}).get("locality") or ""
    if city in ("NOT_AVAILABLE", None):
        city = ""
    allow_fetch = image_policy in ("real_images_plus_design", "ai_recommended", "")

    def fetch_photo(subj: str):
        """AI-fetch a photo of `subj` (school/hospital/mall/metro...) on demand, cached."""
        try:
            from app.business import imagesearch
            p = imagesearch.search_photo(_SUBJECT_QUERY.get(subj, subj), city, cdn_prefix="/cdn/business")
        except Exception:  # noqa: BLE001
            p = None
        if p:
            p["category"] = subj
            ctx_photos.append(p)          # add to pool so it can bind + be reused
        return p

    generic = {"slot": "feature", "role": _P,
               "assets": ["building_interior", "amenity", "landscape", "building_exterior"]}
    for i, sl in enumerate(slides):
        spec = slots[i] if i < len(slots) else generic
        role = spec.get("role", _P)
        prefs = spec.get("assets", [])
        # Context/enrichment slots carry their own subject. Generic "feature" padding
        # slots detect a subject from their HEADLINE (e.g. "Nearby conveniences" -> mall)
        # so they fetch a matching photo. NAMED property slots (hero, kitchen, amenities,
        # floor_plan…) NEVER detect — they always use real property images.
        # Context/enrichment slots carry their subject. A generic "feature" slot fetches
        # ONLY when its HEADLINE explicitly names a nearby place (schools/hospital/mall/
        # metro); otherwise it's property content -> a real PDF image. No lifestyle
        # guessing (that mismatched hospital/school photos onto property slides).
        subject = spec.get("subject")
        if not subject and spec.get("slot") == "feature":
            subject = _detect_subject(sl.get("headline", ""))
        is_map_slot = role == _C and bool(prefs) and prefs[0] in _MAP_TYPES

        if is_map_slot and not subject:
            asset = take_map() or take_ctx(None) or take_real(["building_exterior", "architectural_render"])
        elif subject:
            # TEXT names a real-world subject -> the IMAGE must be that exact subject.
            asset = take_ctx(subject)                    # 1) already-fetched matching photo
            if not asset and allow_fetch:
                asset = fetch_photo(subject) or take_ctx(subject)   # 2) AI-fetch it
            if not asset:                                # 3) map / real image — NEVER a wrong photo
                asset = (take_map() if subject in ("metro",) else None) \
                    or take_real(["building_exterior", "architectural_render", "building_interior"])
        elif role == _C:
            asset = take_ctx(None) or take_map() or take_real(["building_exterior", "architectural_render"])
        else:                                            # property / cta -> real PDF image
            # Gap behaviour by strategy:
            #  real_images_only / ai_recommended -> reuse a real image (never blank),
            #  real_images_plus_design / creative_backgrounds -> clean design background.
            # (Under ai_recommended, feature gaps were already AI-fetched above.)
            reuse = image_policy in ("real_images_only", "ai_recommended") \
                or spec.get("slot") in ("hero", "cta", "floor_plan")
            asset = take_real(prefs, allow_reuse=reuse)
        # stamp the slot identity so the template + copy align with the image
        sl["template"] = spec.get("slot", sl.get("template"))
        sl["slot"] = spec.get("slot")
        if asset:
            sl["image_ref"] = asset.get("cdn_url")
            sl["image_source"] = _ref(asset)
            sl["image_attribution"] = asset.get("attribution", "")
            sl["image_is_context_bg"] = asset.get("asset_type") in CONTEXT_TYPES
            sl["image_asset_type"] = asset.get("asset_type")
            # Small images render 'contained' (never upscaled full-bleed) so they
            # stay sharp — no blur on the slide.
            sl["image_small"] = _min_side(asset) < 900
        else:                                            # no asset -> clean design background
            sl["image_ref"] = None
            sl["image_source"] = None
            sl["image_is_context_bg"] = False
            sl["image_asset_type"] = None
