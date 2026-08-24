"""Business platform API router — namespaced /api/business/* (separate surface).

Kept isolated from the existing Studio API. The final hand-off endpoint
`/api/content/generate` emits the integration contract (Spec §26) the existing
Instagram engine consumes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import re
import unicodedata

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import settings
from app.business import grade as grader
from app.business import ingestion, pipeline, store
from app.business.campaign_brief import CampaignBrief, options as brief_options

router = APIRouter(prefix="/api/business", tags=["business"])

_DATA_DIR = settings.BASE_DIR / "data-business"
# Agent-01 Ingestion accepts ANY raw input and identifies it by content; we no
# longer gate on file extension. Truly unrecognised binaries are still stored but
# flagged non-extractable so Extraction escalates them (never guesses).
_MAX_UPLOAD = 80 * 1024 * 1024  # 80 MB (archives can be large)


def _safe_name(name: str) -> str:
    """Sanitize an uploaded filename: strip paths, keep a readable safe stem."""
    base = Path(name or "document").name
    stem, ext = Path(base).stem, Path(base).suffix.lower()
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9._ -]", "", stem).strip() or "document"
    return f"{stem}{ext}"


class GenerateReq(BaseModel):
    document: str = "DREAMZ (1).pdf"   # filename under data-business/
    goal: str = "site_visit"
    slides: int = 6
    render: bool = True
    grade: bool = False
    persist: bool = True


class StatusReq(BaseModel):
    status: str   # AUTO_APPROVED | REVIEW_REQUIRED | REJECTED


class ExtractReq(BaseModel):
    document: str = "DREAMZ (1).pdf"


class CampaignGenReq(BaseModel):
    property_id: str
    brief: CampaignBrief = CampaignBrief()
    render: bool = True


@router.get("/documents")
def list_documents():
    if not _DATA_DIR.exists():
        return {"documents": []}
    docs = [p.name for p in _DATA_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
    return {"documents": sorted(docs)}


def _store_upload(filename: str, data: bytes) -> dict:
    """Persist one uploaded file (any type) + classify it by content (Agent 01)."""
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(413, f"File too large (>{_MAX_UPLOAD // (1024*1024)} MB).")
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(filename)
    dest = _DATA_DIR / name
    if dest.exists():                       # avoid clobbering an existing file
        stem, suffix = dest.stem, dest.suffix
        i = 2
        while (_DATA_DIR / f"{stem}-{i}{suffix}").exists():
            i += 1
        name = f"{stem}-{i}{suffix}"
        dest = _DATA_DIR / name
    dest.write_bytes(data)
    info = ingestion.classify(dest)
    return {"document": name, "size": len(data), "real_type": info.get("real_type"),
            "category": info.get("category"), "extractable": info.get("extractable"),
            "reason": info.get("reason")}


try:  # python-multipart is required to register a file-upload route
    import multipart as _multipart  # noqa: F401
    _HAS_MULTIPART = True
except Exception:  # noqa: BLE001
    _HAS_MULTIPART = False


async def upload_document(file: UploadFile = File(...)):
    """Drag-and-drop upload of ANY file into data-business/ (type detected by content)."""
    return _store_upload(file.filename or "document", await file.read())


async def upload_documents(files: List[UploadFile] = File(...)):
    """Multi-file upload: accept several files of any type in one request."""
    results = []
    for f in files:
        try:
            results.append(_store_upload(f.filename or "document", await f.read()))
        except HTTPException as exc:
            results.append({"document": f.filename, "error": exc.detail})
    ok = [r for r in results if not r.get("error")]
    return {"uploaded": results, "count": len(ok),
            "documents": [r["document"] for r in ok]}


# Register upload routes only when python-multipart is available, so the app still
# boots on images that predate that dependency (it's in the rebuilt image).
if _HAS_MULTIPART:
    router.post("/documents")(upload_document)
    router.post("/documents/batch")(upload_documents)


@router.post("/generate")
def generate(body: GenerateReq):
    path = _DATA_DIR / body.document
    if not path.exists():
        raise HTTPException(404, f"Document not found: {body.document}")
    try:
        result = pipeline.run(path, goal=body.goal, slides=body.slides, render=body.render)
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))
    if body.grade:
        try:
            result["grade"] = grader.grade(result)
        except Exception as exc:  # noqa: BLE001
            result["grade"] = {"error": str(exc)}
    if body.persist:
        try:
            result["persisted"] = store.save_run(result)
        except Exception as exc:  # noqa: BLE001
            import traceback; traceback.print_exc()
            result["persisted"] = {"error": str(exc)}
    return result


# ---- Dashboard summary (admin home) -----------------------------------------

@router.get("/dashboard/summary")
def dashboard_summary():
    props = store.list_properties(limit=1000)
    campaigns_total = sum(int(p.get("campaigns") or 0) for p in props)
    reviews = 0
    published = 0
    with_verdict = 0
    for p in props:
        v = (p.get("verdict") or {})
        if v.get("status") == "PASS":
            with_verdict += 1
    overview = store.analytics_overview()
    return {
        "properties": len(props),
        "campaigns": campaigns_total,
        "properties_passing": with_verdict,
        "campaigns_tracked": overview.get("campaigns_tracked", 0),
        "top_campaigns": overview.get("top", [])[:5],
        "by_angle": overview.get("by_angle", []),
        "recent_properties": props[:6],
    }


# ---- Campaign Brief control layer (M1) --------------------------------------

@router.get("/brief/options")
def brief_options_endpoint():
    """Allowed values for every campaign control (drives the UI dropdowns)."""
    return brief_options()


@router.post("/extract")
def extract(body: ExtractReq):
    """Stage A — extract & save Property Knowledge once; reuse for many campaigns."""
    path = _DATA_DIR / body.document
    if not path.exists():
        raise HTTPException(404, f"Document not found: {body.document}")
    # Agent-01 gate: unrecognised/unsupported content -> REVIEW_REQUIRED, not a crash.
    info = ingestion.classify(path)
    if not info.get("extractable"):
        raise HTTPException(422, f"Cannot extract '{body.document}' ({info.get('real_type')}): "
                                 f"{info.get('reason', 'unsupported content')} — needs review.")
    try:
        result = pipeline.extract_property(path)
        pid = store.save_property(result["knowledge_model"], result.get("verdict") or {},
                                  result["document"])
        result["property_id"] = pid
        # Version snapshot + changed-fact detection (Spec §35).
        result["version"] = store.snapshot_version(pid, result["knowledge_model"])
        store.audit("DOCUMENT_EXTRACTED", "property", pid, new_value=body.document)
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))
    return result


@router.get("/properties/{property_id}/workspace")
def property_workspace(property_id: str):
    """Aggregate everything for the Property Workspace panel (Spec §29/§34)."""
    prop = store.get_property(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    model = prop.get("model") or {}
    campaigns = prop.get("campaigns", [])
    versions = store.list_versions(property_id)
    overview = {
        "verified_facts": len(model.get("claims", [])),
        "documents": len(model.get("source_documents", [])),
        "media_assets": len(model.get("media", [])),
        "campaigns": len(campaigns),
        "versions": len(versions),
        "confidence": (prop.get("verdict") or {}).get("confidence"),
    }
    return {"property": {"id": prop["id"], "project_name": prop.get("project_name"),
                         "updated_at": prop.get("updated_at")},
            "overview": overview, "knowledge": model, "campaigns": campaigns,
            "versions": versions, "documents": model.get("source_documents", []),
            "media": model.get("media", []), "contacts": model.get("contacts", [])}


@router.get("/properties/{property_id}/versions")
def property_versions(property_id: str):
    return {"versions": store.list_versions(property_id)}


@router.get("/properties/{property_id}/versions/compare")
def compare_versions(property_id: str, from_id: int, to_id: int):
    return store.compare_versions(property_id, from_id, to_id)


@router.post("/campaigns/generate")
def generate_campaign(body: CampaignGenReq):
    """Stage B — generate a campaign from a saved property + Campaign Brief."""
    model = store.get_property_model(body.property_id)
    if not model:
        raise HTTPException(404, f"Property not found: {body.property_id}. Extract it first.")
    try:
        brand = _resolve_brand(body.brief.model_dump())
        result = pipeline.generate_campaign(model, body.brief, render=body.render, brand=brand)
        result["persisted"] = store.save_campaign(body.property_id, body.brief.model_dump(), result)
        result["knowledge_model"] = model
        store.audit("CAMPAIGN_GENERATED", "campaign",
                    result["persisted"].get("campaign_id"), new_value=body.brief.goal)
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))
    return result


# ---- Agent 08 — Batch campaign recommendations (2-3 batches x 6-9 slides) -----

class BatchRecommendReq(BaseModel):
    property_id: str
    batches: int = 3          # how many campaign recommendations (clamped 2..3)
    slides: int = 10          # min slides per carousel (>=10 compulsory; expands to fit all PDF images)
    render: bool = True


# The 3 fixed structures, in priority order (Investor/Value leads — owner's pick).
# (angle, carousel_type, goal, audience) — carousel_type maps to a carousel structure.
_BATCH_STRUCTURES = [
    ("investment_first", "investment", "lead_generation", "investors"),        # -> investor_value
    ("family_first", "property_showcase", "site_visit", "families"),           # -> property_tour
    ("connectivity_first", "location_guide", "site_visit", "young_professionals"),  # -> location_first
]


def _signals(model: dict) -> dict:
    """Which verified facts / real assets exist -> drives strategy scoring (Agent 08)."""
    def _has(v):
        return v not in (None, "", "NOT_AVAILABLE", [])
    loc = model.get("location") or {}
    price = model.get("pricing") or {}
    prop = model.get("property") or {}
    li = model.get("location_intelligence") or {}
    return {
        "floor_plans": len(model.get("floor_plans") or []),
        "amenities": len(model.get("amenities") or []),
        "connectivity": len(model.get("connectivity") or []),
        "location": _has(loc.get("locality")) or _has(loc.get("city")),
        "price": _has(price.get("price")),
        "builder": _has(prop.get("builder")),
        "media": len([m for m in (model.get("media") or []) if m.get("usable")]),
        "hotspots": bool(li.get("context_photos") or li.get("hotspots")),
    }


# (angle, carousel_type, goal, audience, required-signal or None=always-viable)
_STRATEGY_CANDIDATES = [
    ("location_first", "location_guide", "site_visit", "families", "location"),
    ("connectivity_first", "connectivity", "site_visit", "young_professionals", "connectivity"),
    ("amenities_first", "amenities_showcase", "awareness", "families", "amenities"),
    ("floor_plan_first", "floor_plan_breakdown", "brochure", "first_time_home_buyer", "floor_plans"),
    ("price_first", "price_value", "price_enquiry", "budget_buyers", "price"),
    ("investment_first", "investment", "lead_generation", "investors", "price"),
    ("builder_trust", "builder_trust", "awareness", "families", "builder"),
    ("family_first", "family_lifestyle", "site_visit", "families", "amenities"),
    ("project_first", "project_overview", "project_launch", "families", None),
    ("lifestyle_first", "property_showcase", "awareness", "luxury_buyers", None),
]


def _recommend_briefs(model: dict, n: int, slides: int) -> list:
    """Build N briefs, one per fixed 10-slide structure (Investor/Value first). Each
    uses the same verified facts but a distinct proper posting format."""
    briefs = []
    for angle, ctype, goal, audience in _BATCH_STRUCTURES[:n]:
        briefs.append(CampaignBrief(
            goal=goal, target_audience=audience, content_angle=angle, carousel_type=ctype,
            slide_count=slides, language="english", tone="premium", content_density="informative",
            image_policy="real_images_only", claim_policy="strict", generation_mode="controlled",
        ))
    return briefs


@router.post("/campaigns/recommend-batch")
def recommend_batch(body: BatchRecommendReq):
    """Generate 2-3 recommended campaign batches, each a 6-9 slide carousel, from one
    property. Same verified facts -> several distinct, ready-to-review campaigns."""
    model = store.get_property_model(body.property_id)
    if not model:
        raise HTTPException(404, f"Property not found: {body.property_id}. Extract it first.")
    n = max(2, min(3, body.batches))
    slides = max(10, min(12, body.slides))   # >=10 compulsory; carousel expands to fit all images
    briefs = _recommend_briefs(model, n, slides)
    brand = _resolve_brand(briefs[0].model_dump()) if briefs else None
    batches = []
    for i, brief in enumerate(briefs):
        try:
            result = pipeline.generate_campaign(model, brief, render=body.render, brand=brand)
            persisted = store.save_campaign(body.property_id, brief.model_dump(), result)
            store.audit("CAMPAIGN_GENERATED", "campaign", persisted.get("campaign_id"),
                        new_value=f"batch:{brief.goal}")
            slides_out = result.get("carousel", {}).get("slides", [])
            images = result.get("contract", {}).get("carousel", {}).get("images", [])
            batches.append({
                "index": i, "campaign_id": persisted.get("campaign_id"),
                "angle": result.get("marketing", {}).get("angle"),
                "carousel_type": brief.carousel_type, "goal": brief.goal,
                "audience": brief.target_audience, "slides": len(slides_out),
                "rendered_images": len(images), "images": images,
                "caption": result.get("contract", {}).get("caption", ""),
                "hashtags": result.get("contract", {}).get("hashtags", []),
                "claim_violations": result.get("claim_violations", []),
                "status": persisted.get("status"),
                "est_cost_usd": result.get("usage", {}).get("est_cost_usd"),
            })
        except Exception as exc:  # noqa: BLE001
            import traceback; traceback.print_exc()
            batches.append({"index": i, "carousel_type": brief.carousel_type,
                            "error": str(exc), "status": "ERROR"})
    return {"property_id": body.property_id, "requested_batches": n, "slides_per_batch": slides,
            "generated": len([b for b in batches if not b.get("error")]), "batches": batches}


# ---- Custom Poster — build a carousel from user images + details -------------

_CUSTOM_DIR = settings.BASE_DIR / "images" / "business" / "custom"


class CustomSlideIn(BaseModel):
    template: str = "feature"
    headline: str = ""
    subheadline: str = ""
    facts: List[Any] = []
    cta: str = ""
    image: Optional[str] = None      # filename under custom/ or a /cdn URL


class CustomGenReq(BaseModel):
    title: str = "Custom Poster"
    location: str = ""
    builder: str = ""
    contacts: List[dict] = []        # [{name, phone}]
    brand: str = ""
    slides: List[CustomSlideIn] = []


async def custom_upload(files: List[UploadFile] = File(...)):
    """Upload images for a custom poster; returns their cdn refs."""
    _CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        data = await f.read()
        if not data:
            continue
        name = _safe_name(f.filename or "image")
        dest = _CUSTOM_DIR / name
        i = 2
        while dest.exists():
            dest = _CUSTOM_DIR / f"{Path(name).stem}-{i}{Path(name).suffix}"
            i += 1
        dest.write_bytes(data)
        out.append({"filename": dest.name, "cdn_url": f"/cdn/business/custom/{dest.name}"})
    return {"uploaded": out, "count": len(out)}


@router.post("/custom/generate")
def custom_generate(body: CustomGenReq):
    """Render a custom poster/carousel from user-provided images + text, and persist
    it as a campaign so it's editable in the same Slide Editor."""
    import time as _t
    from app.business import rendering
    if not body.slides:
        raise HTTPException(400, "Add at least one slide.")
    slug = "custom-" + (re.sub(r"[^a-z0-9]+", "-", body.title.lower()).strip("-")[:36] or "poster") + "-" + str(int(_t.time()))[-6:]
    media, slides = [], []
    for s in body.slides:
        ref = cdn = None
        if s.image:
            if s.image.startswith("/cdn"):
                cdn = s.image
                ref = str(settings.IMAGES_DIR / s.image.replace("/cdn/", "").lstrip("/"))
            else:
                cdn = f"/cdn/business/custom/{s.image}"
                ref = str(_CUSTOM_DIR / s.image)
            media.append({"asset_type": "custom", "usable": True, "cdn_url": cdn,
                          "storage_ref": ref, "confidence": 1.0})
        slides.append({"template": s.template or "feature", "headline": s.headline,
                       "subheadline": s.subheadline, "facts": s.facts, "cta": s.cta,
                       "image_source": ref, "image_ref": cdn,
                       "image_asset_type": "custom" if ref else None,
                       "image_is_context_bg": False, "locked": False})
    model = {"property": {"id": slug, "project_name": body.title or "Custom Poster",
                          "builder": body.builder or (body.title or "Custom"),
                          "property_type": "", "category": ""},
             "project": {}, "location": {"locality": body.location, "city": body.location},
             "pricing": {"price": "NOT_AVAILABLE"}, "configuration": [], "amenities": [],
             "connectivity": [], "contacts": body.contacts or [], "floor_plans": [],
             "media": media, "claims": [], "source_documents": []}
    out_dir, cdn_prefix = settings.IMAGES_DIR / "business", "/cdn/business"
    brand = _resolve_brand({"brand": body.brand})
    try:
        render = rendering.render_carousel({"carousel": {"slides": slides}}, model,
                                           out_dir=out_dir, cdn_prefix=cdn_prefix, brand=brand)
        pid = store.save_property(model, {"status": "CUSTOM", "confidence": 1.0}, body.title or "Custom Poster")
        campaign = {"carousel": {"slides": slides}, "marketing": {"angle": "custom"},
                    "caption": {}, "contract": {"carousel": {"slides": slides,
                    "images": render.get("images", [])}, "caption": ""},
                    "render": render, "claim_violations": [], "usage": {}, "traces": []}
        persisted = store.save_campaign(pid, {"goal": "custom", "brand": body.brand}, campaign)
        store.audit("CUSTOM_POSTER_GENERATED", "campaign", persisted.get("campaign_id"), new_value=body.title)
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))
    return {"campaign_id": persisted["campaign_id"], "property_id": pid,
            "images": render.get("images", []), "slides": slides, "rendered": render.get("rendered")}


if _HAS_MULTIPART:
    router.post("/custom/upload")(custom_upload)


# ---- persistence / human-in-the-loop review ---------------------------------

@router.get("/properties")
def list_properties(limit: int = 100):
    return {"properties": store.list_properties(limit=limit)}


@router.get("/properties/{property_id}")
def get_property(property_id: str):
    prop = store.get_property(property_id)
    if not prop:
        raise HTTPException(404, "Property not found")
    return prop


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    c = store.get_campaign(campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


@router.put("/campaigns/{campaign_id}/status")
def set_status(campaign_id: int, body: StatusReq):
    if body.status not in ("DRAFT", "AUTO_APPROVED", "REVIEW_REQUIRED", "REJECTED", "PUBLISHED"):
        raise HTTPException(400, "Invalid status")
    if not store.set_campaign_status(campaign_id, body.status):
        raise HTTPException(404, "Campaign not found")
    store.audit("CAMPAIGN_" + body.status, "campaign", campaign_id, new_value=body.status)
    return {"campaign_id": campaign_id, "status": body.status}


# ---- M2/M3: Blueprint preview + per-slide edit / lock / regenerate / reorder ----

class SlideEditReq(BaseModel):
    headline: Optional[str] = None
    subheadline: Optional[str] = None
    facts: Optional[list] = None
    cta: Optional[str] = None
    badges: Optional[list] = None
    template: Optional[str] = None
    image_asset_type: Optional[str] = None
    contacts: Optional[list] = None       # [{name, phone}] shown on CTA slide
    footer: Optional[str] = None          # footer text (builder/brand line)
    brandname: Optional[str] = None       # top-left brand name override
    locality: Optional[str] = None        # top-right locality override


class RegenReq(BaseModel):
    mode: str = "copy"          # copy | image | layout | entire
    render: bool = True


class ReorderReq(BaseModel):
    order: list                 # permutation of slide indices, e.g. [0,2,1,3,4,5,6]
    render: bool = True


def _load_campaign_and_model(campaign_id: int):
    camp = store.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    model = store.get_property_model(camp.get("property_id"))
    if not model:
        raise HTTPException(404, "Property knowledge missing for this campaign")
    carousel = camp.get("carousel") or {"slides": []}
    return camp, model, carousel


def _resolve_brand(brief_dict):
    bid = (brief_dict or {}).get("brand")
    if bid is not None and str(bid).isdigit():
        return store.get_brand(int(bid))
    return None


def _rerender_and_save(camp, carousel, model, render: bool):
    from app import settings
    from app.business import rendering
    out, cdn = settings.IMAGES_DIR / "business", "/cdn/business"
    brand = _resolve_brand(camp.get("brief") or {})
    res = (rendering.render_carousel({"carousel": carousel}, model, out_dir=out, cdn_prefix=cdn, brand=brand)
           if render else {"rendered": False, "images": camp.get("images") or []})
    contract = camp.get("contract") or {}
    contract.setdefault("carousel", {})
    contract["carousel"]["slides"] = carousel.get("slides", [])
    if res.get("images"):
        contract["carousel"]["images"] = res["images"]
    store.update_campaign(camp["id"], carousel=carousel, contract=contract,
                          images=res.get("images") if res.get("images") else None)
    return res, contract


@router.get("/campaigns/{campaign_id}/blueprint")
def get_blueprint(campaign_id: int):
    camp = store.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    carousel = camp.get("carousel") or {"slides": []}
    model = store.get_property_model(camp.get("property_id")) or {}
    return {"campaign_id": campaign_id, "status": camp.get("status"),
            "slides": carousel.get("slides", []), "images": camp.get("images") or [],
            "property_contacts": model.get("contacts", [])}


@router.put("/campaigns/{campaign_id}/slides/{index}")
def edit_slide(campaign_id: int, index: int, body: SlideEditReq, render: bool = False):
    """Edit one slide's copy. Re-renders ONLY that slide (fast) — not the whole carousel."""
    from app.business import rendering, slides as slidesvc
    camp, model, carousel = _load_campaign_and_model(campaign_id)
    try:
        slidesvc.edit_slide(carousel, index, body.model_dump(exclude_none=True))
    except IndexError:
        raise HTTPException(404, "Slide index out of range")
    contract = camp.get("contract") or {}
    images = list((contract.get("carousel") or {}).get("images") or camp.get("images") or [])
    rerendered = False
    if render:
        brand = _resolve_brand(camp.get("brief") or {})
        url = rendering.render_one_slide({"carousel": carousel}, model, index,
                                         out_dir=settings.IMAGES_DIR / "business",
                                         cdn_prefix="/cdn/business", brand=brand)
        if url:
            while len(images) <= index:
                images.append(None)
            images[index] = url
            rerendered = True
    contract.setdefault("carousel", {})
    contract["carousel"]["slides"] = carousel.get("slides", [])
    contract["carousel"]["images"] = images
    store.update_campaign(campaign_id, carousel=carousel, contract=contract, images=images)
    return {"slide": carousel["slides"][index], "rerendered": rerendered, "images": images}


@router.post("/campaigns/{campaign_id}/slides/{index}/lock")
def lock_slide(campaign_id: int, index: int):
    from app.business import slides as slidesvc
    camp, _, carousel = _load_campaign_and_model(campaign_id)
    slidesvc.set_lock(carousel, index, True)
    store.update_campaign(campaign_id, carousel=carousel)
    return {"slide": index, "locked": True}


@router.post("/campaigns/{campaign_id}/slides/{index}/unlock")
def unlock_slide(campaign_id: int, index: int):
    from app.business import slides as slidesvc
    camp, _, carousel = _load_campaign_and_model(campaign_id)
    slidesvc.set_lock(carousel, index, False)
    store.update_campaign(campaign_id, carousel=carousel)
    return {"slide": index, "locked": False}


@router.post("/campaigns/{campaign_id}/slides/{index}/regenerate")
def regenerate_slide(campaign_id: int, index: int, body: RegenReq):
    from app.business import slides as slidesvc
    from app.business.provider import get_provider
    if body.mode not in ("copy", "image", "layout", "entire"):
        raise HTTPException(400, "mode must be copy|image|layout|entire")
    camp, model, carousel = _load_campaign_and_model(campaign_id)
    try:
        slidesvc.regenerate_slide(model, camp.get("brief") or {}, carousel, index,
                                  body.mode, get_provider())
    except IndexError:
        raise HTTPException(404, "Slide index out of range")
    res, _ = _rerender_and_save(camp, carousel, model, body.render)
    return {"slide": carousel["slides"][index], "rerendered": res.get("rendered", False),
            "images": res.get("images", [])}


@router.post("/campaigns/{campaign_id}/blueprint/reorder")
def reorder_blueprint(campaign_id: int, body: ReorderReq):
    from app.business import slides as slidesvc
    camp, model, carousel = _load_campaign_and_model(campaign_id)
    try:
        slidesvc.reorder(carousel, [int(i) for i in body.order])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    res, _ = _rerender_and_save(camp, carousel, model, body.render)
    return {"slides": carousel["slides"], "rerendered": res.get("rendered", False),
            "images": res.get("images", [])}


@router.post("/campaigns/{campaign_id}/render")
def rerender_campaign(campaign_id: int):
    camp, model, carousel = _load_campaign_and_model(campaign_id)
    res, contract = _rerender_and_save(camp, carousel, model, True)
    return {"rendered": res.get("rendered", False), "count": res.get("count", 0),
            "images": res.get("images", []), "contract": contract}


# ---- M4: Brand Presets (Spec §13) -------------------------------------------

class BrandReq(BaseModel):
    name: str = "Brand"
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font: Optional[str] = None
    style: Optional[str] = None
    footer: Optional[str] = None


@router.get("/brands")
def list_brands():
    return {"brands": store.list_brands()}


@router.post("/brands")
def create_brand(body: BrandReq):
    return store.create_brand(body.model_dump(exclude_none=True))


@router.get("/brands/{brand_id}")
def get_brand(brand_id: int):
    b = store.get_brand(brand_id)
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


@router.put("/brands/{brand_id}")
def update_brand(brand_id: int, body: BrandReq):
    b = store.update_brand(brand_id, body.model_dump(exclude_none=True))
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: int):
    if not store.delete_brand(brand_id):
        raise HTTPException(404, "Brand not found")
    return {"deleted": brand_id}


async def upload_brand_logo(brand_id: int, file: UploadFile = File(...)):
    if not store.get_brand(brand_id):
        raise HTTPException(404, "Brand not found")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Logo must be png/jpg/webp")
    data = await file.read()
    if not data or len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "Logo empty or too large (>8MB)")
    logo_dir = settings.IMAGES_DIR / "business" / "brands"
    logo_dir.mkdir(parents=True, exist_ok=True)
    name = f"brand_{brand_id}{ext}"
    (logo_dir / name).write_bytes(data)
    b = store.update_brand(brand_id, {"logo_ref": str(logo_dir / name),
                                      "logo_cdn": f"/cdn/business/brands/{name}"})
    return b


if _HAS_MULTIPART:
    router.post("/brands/{brand_id}/logo")(upload_brand_logo)


# ---- M6 Publishing (Instagram Graph API) + M7 Analytics (Insights) ----------

class PublishReq(BaseModel):
    account_id: int
    dry_run: bool = False   # dry_run builds public URLs + payload WITHOUT posting


class AccountRef(BaseModel):
    account_id: int


def _cdn_to_local(url: str) -> str:
    rel = url.split("/cdn/", 1)[1] if "/cdn/" in url else url.lstrip("/")
    return str(settings.IMAGES_DIR / rel)


@router.get("/accounts")
def business_accounts():
    """Instagram accounts available to publish to (from the rags store)."""
    from app import rags
    return {"accounts": rags.list_accounts(active_only=False)}


@router.post("/campaigns/{campaign_id}/publish")
def publish_campaign(campaign_id: int, body: PublishReq):
    """Bridge an APPROVED campaign -> existing Graph API publisher (Spec §26/§38).

    Publishing is an irreversible outward action; only AUTO_APPROVED campaigns can
    post, and the caller must invoke this explicitly. dry_run returns exactly what
    WOULD be posted (public image URLs + caption) without pushing or posting."""
    from app import db, rags
    from app.services import hosting, instagram
    camp = store.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    if not body.dry_run and camp.get("status") != "AUTO_APPROVED":
        raise HTTPException(400, "Approve the campaign before publishing.")
    account = rags.get_account(body.account_id, with_secret=True)
    if not account:
        raise HTTPException(404, "Instagram account not found")
    contract = camp.get("contract") or {}
    images = (contract.get("carousel") or {}).get("images") or []
    if not images:
        raise HTTPException(400, "Campaign has no rendered slides. Render it first.")
    local_paths = [_cdn_to_local(u) for u in images]
    caption = contract.get("caption") or ""

    # Instagram carousels allow up to IG_MAX_CAROUSEL items PER POST (now 20). A campaign
    # within that limit posts as ONE carousel; anything larger splits into consecutive
    # carousels so EVERY slide is still published.
    _IG_MAX = settings.IG_MAX_CAROUSEL
    chunks = [local_paths[i:i + _IG_MAX] for i in range(0, len(local_paths), _IG_MAX)]
    note = (f"{len(local_paths)} slides exceed Instagram's {_IG_MAX}-per-carousel limit — posting "
            f"as {len(chunks)} carousels ({', '.join(str(len(c)) for c in chunks)} slides)."
            if len(chunks) > 1 else None)

    if body.dry_run:
        return {"dry_run": True, "account": account.get("label"),
                "public_images": [hosting.raw_url(p) for p in local_paths],
                "caption": caption, "slides": len(local_paths), "posts": len(chunks), "note": note}
    posts, first_public = [], []
    try:
        for ci, chunk in enumerate(chunks):
            cap = caption if len(chunks) == 1 else f"{caption}\n\n(Part {ci + 1} of {len(chunks)})"
            public = hosting.publish_images(chunk, commit_msg=f"Business campaign {campaign_id} part {ci + 1}")
            result = instagram.publish(account, public, cap)
            posts.append(result)
            if ci == 0:
                first_public = public
            db.save_published_post(
                account_id=account.get("id"), account_label=account.get("label"),
                niche="realestate", caption=cap, media_type=result.get("media_type"),
                ig_media_id=result.get("ig_media_id"), permalink=result.get("permalink"),
                cover_url=public[0] if public else None, slide_urls=public)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Publish failed: {exc}")
    primary = posts[0]
    contract["published"] = {"ig_media_id": primary.get("ig_media_id"),
                             "permalink": primary.get("permalink"),
                             "posts": [{"ig_media_id": p.get("ig_media_id"), "permalink": p.get("permalink")} for p in posts],
                             "account_id": account.get("id"), "account_label": account.get("label")}
    store.update_campaign(campaign_id, contract=contract)
    store.set_campaign_status(campaign_id, "PUBLISHED")
    store.audit("CAMPAIGN_PUBLISHED", "campaign", campaign_id, new_value=primary.get("permalink"))
    return {"success": True, **primary, "public_images": first_public, "slides": len(local_paths),
            "posts": len(posts), "permalinks": [p.get("permalink") for p in posts], "note": note}


@router.post("/campaigns/{campaign_id}/analytics/sync")
def sync_analytics(campaign_id: int, body: AccountRef):
    """Pull Instagram Insights for a published campaign and store them (M7)."""
    from app import rags
    from app.business import analytics
    camp = store.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    published = (camp.get("contract") or {}).get("published") or {}
    media_id = published.get("ig_media_id")
    if not media_id:
        raise HTTPException(400, "Campaign is not published yet (no media id).")
    account = rags.get_account(body.account_id, with_secret=True)
    if not account:
        raise HTTPException(404, "Instagram account not found")
    try:
        metrics = analytics.fetch_media_insights(account, media_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Insights failed: {exc}")
    score = analytics.score_campaign(metrics)
    store.save_analytics(campaign_id, camp.get("property_id"), media_id,
                         published.get("permalink"), account.get("label"), metrics, score)
    store.audit("ANALYTICS_SYNCED", "campaign", campaign_id, new_value=str(score))
    return {"campaign_id": campaign_id, "media_id": media_id, "metrics": metrics, "score": score}


@router.get("/analytics/campaigns/{campaign_id}")
def campaign_analytics(campaign_id: int):
    return {"campaign_id": campaign_id, "history": store.get_analytics_for_campaign(campaign_id)}


@router.get("/analytics/overview")
def analytics_overview():
    return store.analytics_overview()


# ---- Media Library (aggregated real extracted assets, panel 12) --------------

@router.get("/media")
def media_library(category: Optional[str] = None):
    items = []
    for p in store.list_properties(limit=1000):
        model = store.get_property_model(p["id"]) or {}
        for m in model.get("media", []):
            if not m.get("cdn_url"):
                continue
            if category and m.get("asset_type") != category:
                continue
            items.append({"property_id": p["id"], "project_name": p.get("project_name"),
                          "asset_type": m.get("asset_type"), "cdn_url": m.get("cdn_url"),
                          "resolution": m.get("resolution"), "confidence": m.get("confidence")})
    cats = sorted({i["asset_type"] for i in items})
    return {"media": items, "categories": cats, "count": len(items)}


# ---- Integrations status (panel 22) -----------------------------------------

@router.get("/github/status")
def github_status():
    """Live check: is the GitHub token valid for the configured repo? (Settings UI)"""
    from app.services import hosting
    return hosting.check_repo_access()


@router.get("/integrations/status")
def integrations_status():
    from app import rags
    accs = rags.list_accounts(active_only=False)
    return {
        "openai": {"connected": bool(settings.OPENAI_API_KEY), "model": settings.OPENAI_MODEL},
        "instagram_accounts": [{"id": a["id"], "label": a["label"], "handle": a.get("handle"),
                                "has_token": a.get("has_token"), "niche": a.get("niche")} for a in accs],
        "docling": settings.__dict__.get("BUSINESS_USE_DOCLING", None) or __import__("os").getenv("BUSINESS_USE_DOCLING", "0"),
        "database": "postgresql",
    }


class ContentReq(BaseModel):
    document: str = "DREAMZ (1).pdf"
    goal: str = "site_visit"
    slides: int = 6


# The clean integration boundary the EXISTING Instagram engine consumes (Spec §26).
@router.post("/content/generate", tags=["integration"])
def content_generate(body: ContentReq):
    path = _DATA_DIR / body.document
    if not path.exists():
        raise HTTPException(404, f"Document not found: {body.document}")
    result = pipeline.run(path, goal=body.goal, slides=body.slides, render=True)
    return result["contract"]
