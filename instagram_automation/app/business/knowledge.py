"""Intelligence stage — Property Entity (04) + Multimodal Vision (03) + Verification (05).

Maps extracted evidence into the Property Knowledge Model via the API LLM
(structured output over ONLY the relevant extracted text — never raw files),
classifies real image crops with the vision model, then runs a DETERMINISTIC
evidence check: any claim whose cited span cannot be located in the source is
dropped, and any missing fact becomes the literal `NOT_AVAILABLE`. No fact is ever
invented (Spec §1, §10).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.business.extraction import ExtractionBundle
from app.business.provider import LLMProvider

ASSET_LABELS = [
    "building_exterior", "building_interior", "living_room", "bedroom", "kitchen",
    "bathroom", "balcony", "amenity", "kids_area", "sports", "parking", "landscape",
    "floor_plan", "site_plan", "cluster_plan", "location_map", "logo", "builder_logo",
    "architectural_render", "document_scan", "unknown",
]

_ENTITY_SYSTEM = (
    "You are a real-estate document analyst. You map ONLY the provided extracted "
    "text into structured property data. You NEVER invent a value that is not "
    "present in the text. If a field is not clearly stated, output the string "
    '"NOT_AVAILABLE" (for numbers use null). For every factual field you fill, add '
    "a claim citing the exact source substring and page it came from. Respond with "
    "strict JSON only."
)


def _entity_prompt(bundle: ExtractionBundle) -> str:
    return (
        "From the extracted brochure text below, produce JSON exactly of shape:\n"
        "{\n"
        '  "project_name","builder","developer","property_type"(apartment|villa|plot|'
        'site|land|commercial|rental|resale),"category"(budget|mid|premium|luxury),'
        '"status"(new|under_construction|ready|resale),\n'
        '  "location":{"address","city","locality","pincode","landmark"},\n'
        '  "project":{"land_area","total_units":int|null,"floors":int|null,"blocks":int|null},\n'
        '  "configuration":[{"bhk","label","area_sqft":number|null,"rooms":[{"name","dimensions"}]}],\n'
        '  "pricing":{"price": <string or "NOT_AVAILABLE">},\n'
        '  "amenities":[string], "connectivity":[{"name","distance"}], "approvals":[string],\n'
        '  "views":[string], "features":[string], "contacts":[{"name","phone"}],\n'
        '  "claims":[{"field","value","source_page":int,"source_text": "<exact substring>"}]\n'
        "}\n"
        "Rules: only use facts present in the text; missing -> NOT_AVAILABLE/null; "
        "NEVER guess price, RERA, distances, unit counts, or dimensions.\n"
        "Guidance: the BUILDER/DEVELOPER is the company name behind the project — "
        "usually found near 'About <Company>', a company logo/title, or the site "
        "address block (e.g. 'About Landmark Homes' -> builder = 'Landmark Homes'). "
        "The project_name (e.g. 'Landmark Dreamz') and the builder can differ.\n"
        "Include claims for at least: project_name, builder, total_units, land_area, "
        "area_sqft, approvals, each contact phone.\n\n"
        "=== EXTRACTED TEXT ===\n" + bundle.page_tagged_text()
    )


def extract_entities(bundle: ExtractionBundle, provider: LLMProvider) -> Dict[str, Any]:
    raw = provider.structured_output(system=_ENTITY_SYSTEM, user=_entity_prompt(bundle),
                                     max_tokens=3000)
    raw.setdefault("claims", [])
    raw["_trace"] = {"agent": "04-property-entity", "fields": len(raw)}
    return raw


def classify_images(bundle: ExtractionBundle, provider: LLMProvider) -> List[Dict[str, Any]]:
    """Vision stage (03): classify each REAL image crop into the asset taxonomy."""
    assets: List[Dict[str, Any]] = []
    for pg in bundle.pages:
        for region in pg.images:
            data = Path(region.storage_ref).read_bytes()
            verdict = provider.classify_image(
                image_bytes=data, mime="image/png", labels=ASSET_LABELS,
                instruction=("Classify this cropped image from a real-estate brochure "
                             f"(page {region.page})."),
            )
            assets.append({
                "asset_type": verdict.get("label", "unknown"),
                "page": region.page, "bbox": region.bbox,
                "resolution": f"{region.width}x{region.height}",
                "storage_ref": region.storage_ref, "cdn_url": region.cdn_url,
                "usable": region.width >= 200 and region.height >= 150,
                "confidence": round(float(verdict.get("confidence", 0.0)), 2),
                "source": {"document": bundle.document, "page": region.page, "method": "vision"},
            })
    return assets


# ===================== VERIFICATION (05) — deterministic evidence gate ==========

def _as_text(v: Any) -> str:
    return "" if v is None else str(v)


def validate(entities: Dict[str, Any], bundle: ExtractionBundle,
             assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Drop unsupported claims, mark missing as NOT_AVAILABLE, score confidence,
    and assemble the validated Property Knowledge Model + verdict."""
    warnings: List[str] = []
    errors: List[str] = []
    verified_claims: List[Dict[str, Any]] = []
    confidence: Dict[str, float] = {}

    for c in entities.get("claims", []):
        field = c.get("field", "")
        val = c.get("value")
        src_text = _as_text(c.get("source_text"))
        src_page = c.get("source_page")
        text_ok = bundle.find_span(src_text, src_page) if src_text else False
        value_ok = bundle.find_span(_as_text(val)) if val not in (None, "") else False
        if text_ok and value_ok:
            conf = 0.97
        elif text_ok or value_ok:
            conf = 0.82
        else:
            warnings.append(f"Unsupported claim dropped: {field}={val!r} (no evidence).")
            continue
        verified_claims.append({
            "field": field, "value": val, "confidence": conf,
            "source": {"document": bundle.document, "page": src_page, "text": src_text,
                       "method": "digital_text"},
        })
        confidence[field] = conf

    # --- pricing: the critical NOT_AVAILABLE correctness gate ---------------
    price = (entities.get("pricing") or {}).get("price")
    if not price or _norm(price) in ("not_available", "none", "null", ""):
        price = "NOT_AVAILABLE"
    elif not bundle.find_span(_as_text(price)):
        warnings.append("Price proposed by model has no source evidence -> NOT_AVAILABLE.")
        price = "NOT_AVAILABLE"
    confidence["pricing.price"] = 0.0 if price == "NOT_AVAILABLE" else 0.9

    # --- assemble validated model (schema-shaped) --------------------------
    loc = entities.get("location") or {}
    proj = entities.get("project") or {}
    model = {
        "property": {
            "id": _slug(entities.get("project_name")),
            "project_name": entities.get("project_name") or "NOT_AVAILABLE",
            "property_type": entities.get("property_type") or "NOT_AVAILABLE",
            "category": entities.get("category") or "NOT_AVAILABLE",
            "status": entities.get("status") or "NOT_AVAILABLE",
            "builder": entities.get("builder") or "NOT_AVAILABLE",
            "developer": entities.get("developer") or entities.get("builder") or "NOT_AVAILABLE",
        },
        "location": {k: (loc.get(k) or "NOT_AVAILABLE") for k in
                     ("address", "city", "locality", "pincode", "landmark")}
                    | {"latitude": None, "longitude": None},
        "configuration": entities.get("configuration") or [],
        "pricing": {"price": price, "price_min": None, "price_max": None,
                    "price_per_sqft": None, "currency": "INR"},
        "project": {"land_area": proj.get("land_area") or "NOT_AVAILABLE",
                    "total_units": proj.get("total_units"),
                    "floors": proj.get("floors"), "blocks": proj.get("blocks")},
        "amenities": entities.get("amenities") or [],
        "connectivity": [
            {"name": n.get("name"), "distance": n.get("distance"),
             "distance_kind": "SOURCE_DOCUMENT_DISTANCE",
             "source": {"document": bundle.document}}
            for n in (entities.get("connectivity") or []) if n.get("name")
        ],
        "approvals": entities.get("approvals") or [],
        "features": entities.get("features") or [],
        "views": entities.get("views") or [],
        "floor_plans": [a for a in assets if a["asset_type"] in ("floor_plan", "site_plan")],
        "media": assets,
        "contacts": [
            {"name": c.get("name"), "phone": c.get("phone"), "role": "sales",
             "source": {"document": bundle.document}}
            for c in (entities.get("contacts") or []) if c.get("phone")
        ],
        "source_documents": [bundle.document],
        "claims": verified_claims,
        "conflicts": [],
        "confidence": confidence,
    }

    # --- verdict -----------------------------------------------------------
    if model["property"]["project_name"] == "NOT_AVAILABLE":
        errors.append("No project name could be verified.")
    status = "REVIEW_REQUIRED" if (errors or len(verified_claims) < 2) else "PASS"
    verdict = {"status": status, "confidence": round(
        sum(confidence.values()) / max(1, len(confidence)), 2),
        "warnings": warnings, "errors": errors}
    model["_verdict"] = verdict
    model["_trace"] = {"agent": "05-verification", "claims_verified": len(verified_claims),
                       "claims_dropped": len(warnings)}
    return model


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", _as_text(s).lower()).strip()


def _slug(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _as_text(s).lower()).strip("-") or "property"
