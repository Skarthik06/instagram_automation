"""Agent 15 — Location Intelligence & Asset Acquisition.

Turns the verified location into FACTUAL context assets that enrich carousels
without fabricating property visuals (Spec §15/§16/§18):
  * geocode the locality (Nominatim),
  * discover real nearby hotspots — metro/malls/hospitals/schools/parks (Overpass),
  * render a REAL OpenStreetMap static map with markers (tile fetch + Pillow).

All free, no API key, cached on disk, and network-guarded (degrades to
brochure-only assets if offline). Only a public place NAME is ever sent out —
never PII. Distances derived here are CALCULATED_DISTANCE, kept distinct from the
brochure's SOURCE_DOCUMENT_DISTANCE.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw

from app import settings

_ENRICH_ON = os.getenv("BUSINESS_ENRICH", "1").strip() not in ("0", "false", "")
_TILE_URL = os.getenv("OSM_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
_UA = {"User-Agent": "InstagramBusiness-RealEstate/1.0 (property marketing prototype)"}
_CACHE = settings.IMAGES_DIR / "business" / "_enrich_cache"
_TILES = settings.IMAGES_DIR / "business" / "_tiles"
_TIMEOUT = 12

_CATEGORY_TAGS = {
    "metro": [("railway", "station"), ("station", "subway")],
    "mall": [("shop", "mall")],
    "hospital": [("amenity", "hospital")],
    "school": [("amenity", "school")],
    "park": [("leisure", "park")],
    "supermarket": [("shop", "supermarket")],
}


def _cache_get(key: str) -> Optional[Any]:
    p = _CACHE / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


def _cache_put(key: str, value: Any) -> None:
    _CACHE.mkdir(parents=True, exist_ok=True)
    (_CACHE / f"{key}.json").write_text(json.dumps(value), encoding="utf-8")


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:24]


# ---- geo math ------------------------------------------------------------
def _deg2num(lat: float, lon: float, z: int) -> Tuple[float, float]:
    lat_r = math.radians(lat)
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    R = 6371.0
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    x = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return round(R * 2 * math.asin(math.sqrt(x)), 2)


# ---- external geodata ----------------------------------------------------
def geocode(query: str) -> Optional[Dict[str, Any]]:
    key = "geo_" + _hash(query)
    cached = _cache_get(key)
    if cached is not None:
        return cached or None
    for attempt in range(2):  # one retry for transient failures / rate limits
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": query, "format": "json", "limit": 1},
                             headers=_UA, timeout=_TIMEOUT)
            time.sleep(1.1)  # Nominatim usage policy: <=1 req/s
            if r.status_code != 200:
                time.sleep(1.5)
                continue
            data = r.json()
            if not data:
                _cache_put(key, {})  # genuine no-result for this exact phrasing
                return None
            hit = data[0]
            out = {"lat": float(hit["lat"]), "lon": float(hit["lon"]),
                   "display_name": hit.get("display_name", ""), "source": "OpenStreetMap/Nominatim"}
            _cache_put(key, out)
            return out
        except Exception:  # noqa: BLE001
            time.sleep(1.0)
    return None  # transient — do NOT cache, so a later run can retry


def geocode_best(model_location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Try several query phrasings (most→least specific) until one resolves."""
    loc = model_location or {}

    def ok(v: Any) -> Optional[str]:
        return v if v and v != "NOT_AVAILABLE" else None

    locality, city = ok(loc.get("locality")), ok(loc.get("city"))
    landmark, pincode = ok(loc.get("landmark")), ok(loc.get("pincode"))
    candidates: List[str] = []
    if locality and city:
        candidates.append(f"{locality}, {city}")
    if locality:
        candidates.append(locality)
        # most-specific token of a comma/"post"-laden locality, e.g. "Singapura"
        token = locality.replace(" Post", "").split(",")[0].strip()
        if token and city:
            candidates.append(f"{token}, {city}")
    if pincode and city:
        candidates.append(f"{city} {pincode}")
    if landmark and city:
        candidates.append(f"{landmark}, {city}")
    if city:
        candidates.append(city)
    seen = set()
    for q in candidates:
        if q in seen:
            continue
        seen.add(q)
        hit = geocode(q)
        if hit:
            hit = dict(hit)
            hit["query"] = q
            return hit
    return None


def nearby_hotspots(lat: float, lon: float, radius_m: int = 5000,
                    per_category: int = 3) -> List[Dict[str, Any]]:
    key = "poi_" + _hash(f"{lat:.4f},{lon:.4f},{radius_m}")
    cached = _cache_get(key)
    if cached is not None:
        return cached
    clauses = []
    for cat, tags in _CATEGORY_TAGS.items():
        for k, v in tags:
            clauses.append(f'node(around:{radius_m},{lat},{lon})["{k}"="{v}"];')
    q = f"[out:json][timeout:25];({''.join(clauses)});out center 60;"
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    headers = {**_UA, "Accept": "application/json", "Content-Type": "text/plain; charset=utf-8"}
    elements = None
    for attempt, ep in enumerate(endpoints):
        try:
            r = requests.post(ep, data=q.encode("utf-8"), headers=headers, timeout=25)
            if r.status_code == 200:
                elements = r.json().get("elements", [])
                break
            time.sleep(1.5)  # throttled/refused -> try next mirror
        except Exception:  # noqa: BLE001
            time.sleep(1.0)
    if not elements:  # best-effort: never block the pipeline on Overpass
        return []

    def cat_of(tags: Dict[str, str]) -> str:
        for cat, pairs in _CATEGORY_TAGS.items():
            for k, v in pairs:
                if tags.get(k) == v:
                    return cat
        return "place"

    found: List[Dict[str, Any]] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None or plon is None:
            continue
        found.append({"name": name, "category": cat_of(tags),
                      "lat": float(plat), "lon": float(plon),
                      "distance_km": haversine_km((lat, lon), (float(plat), float(plon))),
                      "distance_kind": "CALCULATED_DISTANCE", "source": "OpenStreetMap"})
    # nearest N per category
    out: List[Dict[str, Any]] = []
    for cat in _CATEGORY_TAGS:
        items = sorted([f for f in found if f["category"] == cat], key=lambda x: x["distance_km"])
        out.extend(items[:per_category])
    out.sort(key=lambda x: x["distance_km"])
    _cache_put(key, out)
    return out


# ---- real static map (OSM tiles) ----------------------------------------
def _fetch_tile(z: int, x: int, y: int) -> Optional[Image.Image]:
    tp = _TILES / str(z) / str(x) / f"{y}.png"
    if tp.exists():
        try:
            return Image.open(tp).convert("RGB")
        except Exception:  # noqa: BLE001
            pass
    try:
        url = _TILE_URL.format(z=z, x=x, y=y)
        r = requests.get(url, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        tp.parent.mkdir(parents=True, exist_ok=True)
        img.save(tp)
        time.sleep(0.05)
        return img
    except Exception:  # noqa: BLE001
        return None


def render_map(center: Tuple[float, float], markers: List[Dict[str, Any]], *,
               out_path: Path, zoom: int = 13, w: int = 1080, h: int = 1080) -> Optional[str]:
    lat, lon = center
    cx, cy = _deg2num(lat, lon, zoom)
    cpx, cpy = cx * 256, cy * 256
    left, top = cpx - w / 2, cpy - h / 2
    canvas = Image.new("RGB", (w, h), (233, 231, 225))
    x0t, x1t = int(left // 256), int((left + w) // 256)
    y0t, y1t = int(top // 256), int((top + h) // 256)
    ok = False
    for tx in range(x0t, x1t + 1):
        for ty in range(y0t, y1t + 1):
            tile = _fetch_tile(zoom, tx, ty)
            if tile is None:
                continue
            ok = True
            canvas.paste(tile, (int(tx * 256 - left), int(ty * 256 - top)))
    if not ok:
        return None
    draw = ImageDraw.Draw(canvas, "RGBA")

    def to_px(la: float, lo: float) -> Tuple[int, int]:
        mx, my = _deg2num(la, lo, zoom)
        return int(mx * 256 - left), int(my * 256 - top)

    # hotspot markers
    for m in markers:
        px, py = to_px(m["lat"], m["lon"])
        if -20 <= px <= w + 20 and -20 <= py <= h + 20:
            draw.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(14, 42, 59, 235), outline=(255, 255, 255, 255), width=2)
    # property marker (gold star-ish)
    px, py = w // 2, h // 2
    draw.ellipse([px - 17, py - 17, px + 17, py + 17], fill=(199, 154, 58, 255), outline=(255, 255, 255, 255), width=3)
    draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(14, 42, 59, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return str(out_path)


# ---- orchestration -------------------------------------------------------
def enrich_location(model: Dict[str, Any], *, out_dir: Path, cdn_prefix: str) -> Dict[str, Any]:
    """Produce location_intelligence for a validated model. Safe/degrading."""
    result: Dict[str, Any] = {"enabled": _ENRICH_ON, "geocode": None, "hotspots": [],
                              "map_asset": None, "_trace": {"agent": "15-location-intelligence"}}
    if not _ENRICH_ON:
        return result
    geo = geocode_best(model.get("location", {}))
    if not geo:
        result["_trace"]["note"] = "geocode failed for all query variants"
        return result
    result["geocode"] = geo
    center = (geo["lat"], geo["lon"])
    hotspots = nearby_hotspots(*center)
    result["hotspots"] = hotspots

    slug = _hash(model["property"]["id"], f"{center[0]:.4f}")
    map_path = out_dir / "maps" / f"map_{slug}.png"
    rendered = render_map(center, hotspots, out_path=map_path, w=1080, h=1080)
    if rendered:
        result["map_asset"] = {
            "asset_type": "context_map", "provenance": "derived",
            "storage_ref": rendered, "cdn_url": f"{cdn_prefix}/maps/{map_path.name}",
            "attribution": "© OpenStreetMap contributors", "usable": True,
        }
    # Fetch REAL high-res photos matching the discovered hotspot categories
    # (metro/mall/school...) so context slides show the actual subject (Agent 16).
    try:
        from app.business import imagesearch
        city = (model.get("location") or {}).get("city", "")
        result["context_photos"] = imagesearch.fetch_context_photos(
            hotspots, city if city != "NOT_AVAILABLE" else "", cdn_prefix=cdn_prefix)
    except Exception as exc:  # noqa: BLE001
        result["context_photos"] = []
        result["_trace"]["photos_error"] = str(exc)

    result["_trace"].update({"geocoded": True, "hotspots": len(hotspots),
                             "map": bool(rendered), "context_photos": len(result.get("context_photos", []))})
    return result
