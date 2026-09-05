"""Agent 16 — Context Image Acquisition (Spec §15/§16 context, §18 attraction).

Given the AI-discovered nearby-hotspot text (metro / mall / hospital / school + city),
fetch REAL, high-resolution, commercially-licensed photos that MATCH the slide subject
so a connectivity slide actually shows a metro, a school slide shows a school, etc.

Sources (tried in order, results merged and the largest usable image wins):
  1. Openverse  (api.openverse.org)          — CC/PD, commercial filter, no key
  2. Wikimedia Commons (commons.wikimedia.org) — huge free media corpus, no key
Both return an attribution + license which we keep and print on CONTEXT slides only
(never used to misrepresent the property). A missing photo degrades to the map.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from app import settings

_ON = os.getenv("BUSINESS_FETCH_PHOTOS", "1").strip() not in ("0", "false", "")
# Wikimedia's UA policy REQUIRES a descriptive agent with a contact URL, else it
# returns HTTP 429. A generic UA gets rate-limited, so we identify the tool + repo.
_UA = {"User-Agent": "InstagramBusiness-RealEstate/1.0 "
                     "(+https://github.com/skarthik06/instagram_automation; real-estate marketing)"}
_CACHE = settings.IMAGES_DIR / "business" / "_fetched"
_META = _CACHE / "_meta"
_OPENVERSE = "https://api.openverse.org/v1/images/"
_COMMONS = "https://commons.wikimedia.org/w/api.php"

_MIN_W, _MIN_H = 700, 500

# hotspot category -> one or more broad visual search phrases (first that yields a
# usable image wins). Multiple phrases give metro/transit better odds of a match.
_QUERY: Dict[str, List[str]] = {
    "metro": ["metro station", "subway station platform", "rapid transit station"],
    "mall": ["shopping mall", "shopping centre interior"],
    "hospital": ["hospital building", "hospital exterior"],
    "school": ["school building", "school campus"],
    "park": ["city park", "urban park"],
    "supermarket": ["supermarket", "grocery store aisle"],
    "airport": ["airport terminal"],
    "railway": ["railway station"],
    "bus": ["bus station"],
    "restaurant": ["restaurant interior"],
    "gym": ["fitness gym interior"],
}

_TAG_RE = re.compile(r"<[^>]+>")


def _hash(*p: str) -> str:
    h = hashlib.sha256()
    for x in p:
        h.update(str(x).encode("utf-8"))
    return h.hexdigest()[:20]


def _clean(text: str) -> str:
    """Strip HTML (Wikimedia artist fields are HTML) and collapse whitespace."""
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text or "")).strip()


def _openverse_candidates(query: str) -> List[Dict[str, Any]]:
    """Normalised candidate dicts from Openverse for one query phrase."""
    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(_OPENVERSE, params={"q": query, "license_type": "commercial,modification",
                                             "page_size": 8, "mature": "false"},
                         headers=_UA, timeout=15)
        r.raise_for_status()
        for hit in r.json().get("results", []):
            if not hit.get("url"):
                continue
            out.append({
                "img_url": hit["url"], "width": hit.get("width") or 0, "height": hit.get("height") or 0,
                "creator": hit.get("creator") or "Openverse", "license": (hit.get("license") or "").upper(),
                "source_url": hit.get("foreign_landing_url"), "source": "Openverse",
            })
    except Exception:  # noqa: BLE001
        pass
    return out


def _commons_candidates(query: str) -> List[Dict[str, Any]]:
    """Normalised candidate dicts from Wikimedia Commons for one query phrase.

    Uses a generator search over the File namespace and pulls a 1600px thumbnail
    URL plus license/artist metadata — no API key required."""
    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(_COMMONS, params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 10,
            "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
        }, headers=_UA, timeout=15)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            # Skip non-photographic media (svg/gif icons, maps, diagrams).
            if url.lower().rsplit(".", 1)[-1] in ("svg", "gif", "pdf", "tif", "tiff"):
                continue
            meta = info.get("extmetadata") or {}
            license_name = _clean((meta.get("LicenseShortName") or {}).get("value", ""))
            artist = _clean((meta.get("Artist") or {}).get("value", "")) or "Wikimedia Commons"
            out.append({
                "img_url": url,
                "width": info.get("thumbwidth") or info.get("width") or 0,
                "height": info.get("thumbheight") or info.get("height") or 0,
                "creator": artist[:60], "license": license_name.upper(),
                "source_url": info.get("descriptionurl"), "source": "Wikimedia Commons",
            })
    except Exception:  # noqa: BLE001
        pass
    return out


def _get(url: str, timeout: int = 20) -> requests.Response:
    """GET with one polite retry on 429 (rate-limit), honouring Retry-After."""
    r = requests.get(url, headers=_UA, timeout=timeout)
    if r.status_code == 429:
        wait = min(float(r.headers.get("Retry-After") or 1.5), 3.0)
        time.sleep(wait)
        r = requests.get(url, headers=_UA, timeout=timeout)
    return r


def _download_best(candidates: List[Dict[str, Any]], key: str, cdn_prefix: str) -> Optional[Dict[str, Any]]:
    """Download the largest usable candidate; save + return its asset dict."""
    seen: set = set()
    uniq: List[Dict[str, Any]] = []
    for c in candidates:
        if c["img_url"] in seen:
            continue
        seen.add(c["img_url"])
        uniq.append(c)
    uniq.sort(key=lambda x: (x.get("width") or 0) * (x.get("height") or 0), reverse=True)
    for c in uniq[:8]:
        try:
            img = _get(c["img_url"], timeout=20)
            img.raise_for_status()
            pil = Image.open(BytesIO(img.content)).convert("RGB")
            if pil.width < _MIN_W or pil.height < _MIN_H:
                continue
            _CACHE.mkdir(parents=True, exist_ok=True)
            _META.mkdir(parents=True, exist_ok=True)
            name = f"ctx_{key}.jpg"
            pil.save(_CACHE / name, quality=92)
            lic = f" · {c['license']}" if c.get("license") else ""
            return {
                "asset_type": "context_photo", "provenance": "fetched",
                "storage_ref": str(_CACHE / name), "cdn_url": f"{cdn_prefix}/_fetched/{name}",
                "attribution": f"Photo: {c['creator']}{lic} ({c['source']})",
                "source_url": c.get("source_url"), "usable": True, "confidence": 0.6,
                "resolution": f"{pil.width}x{pil.height}",
            }
        except Exception:  # noqa: BLE001
            continue
    return None


def search_photo(subject: str, city: str = "", *, cdn_prefix: str = "/cdn/business",
                 phrases: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Fetch one high-res commercial-licensed photo matching `subject`.

    Gathers candidates from Openverse AND Wikimedia Commons across city-qualified
    and broad phrasings, then downloads the largest usable one. Cached (both hits
    and misses) so a slow multi-source search runs once per subject+city."""
    if not _ON:
        return None
    key = _hash("v2", subject, city)
    meta_path = _META / f"{key}.json"
    if meta_path.exists():
        try:
            cached = json.loads(meta_path.read_text(encoding="utf-8"))
            if cached and Path(cached.get("storage_ref", "")).exists():
                return cached
            if cached == {}:
                return None
        except Exception:  # noqa: BLE001
            pass

    base_phrases = phrases or [subject]
    queries: List[str] = []
    for ph in base_phrases:
        if city:
            queries.append(f"{city} {ph}".strip())
        queries.append(ph)
    # de-dup, preserve order
    queries = list(dict.fromkeys(q for q in queries if q))

    candidates: List[Dict[str, Any]] = []
    for q in queries:
        candidates += _openverse_candidates(q)
    for q in queries:
        candidates += _commons_candidates(q)

    result = _download_best(candidates, key, cdn_prefix)
    if result:
        result["subject"] = subject
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(result), encoding="utf-8")
        return result
    _META.mkdir(parents=True, exist_ok=True)
    meta_path.write_text("{}", encoding="utf-8")
    return None


def fetch_context_photos(hotspots: List[Dict[str, Any]], city: str = "",
                         *, cdn_prefix: str = "/cdn/business", max_photos: int = 6) -> List[Dict[str, Any]]:
    """One representative high-res photo per distinct hotspot category present."""
    if not _ON or not hotspots:
        return []
    seen: set = set()
    photos: List[Dict[str, Any]] = []
    for h in hotspots:
        cat = h.get("category")
        if cat in seen or cat not in _QUERY:
            continue
        seen.add(cat)
        phrases = _QUERY[cat]
        p = search_photo(phrases[0], city, cdn_prefix=cdn_prefix, phrases=phrases)
        if p:
            p["category"] = cat
            photos.append(p)
        if len(photos) >= max_photos:
            break
    return photos
