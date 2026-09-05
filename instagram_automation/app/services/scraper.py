"""Aesthetic background scraper (Pinterest) for the Quotes niche.

Scrapes candidate images, rejects low-res / watermarked / text-heavy ones,
then ranks the rest by sharpness, saturation and size. News infographics are
generated (see render.py) and do not use this module.
"""
from __future__ import annotations

import asyncio
import math
import random
import re
from io import BytesIO
from typing import Dict, List, Optional

import cv2
import numpy as np
import requests
from PIL import Image, ImageOps

try:
    import pytesseract
except Exception:  # OCR optional; watermark check degrades gracefully
    pytesseract = None

from playwright.sync_api import sync_playwright

DEFAULT_LIMIT = 8
MIN_WIDTH = 600
MIN_HEIGHT = 600
REQUEST_TIMEOUT = 8
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_UA = {"User-Agent": _BROWSER_UA}

# Pinterest serves tiny thumbnails (e.g. /60x60/); rewrite the size segment to a
# full-resolution variant of the SAME pin so the ranked image is usable as a bg.
_PINIMG_RE = re.compile(r"(i\.pinimg\.com/)[^/]+/")


def _upgrade_pinimg_url(url: str) -> str:
    if "i.pinimg.com" in url:
        return _PINIMG_RE.sub(r"\g<1>736x/", url, count=1)
    return url


# ===================== shared image helpers =====================

def download_image_bytes(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def _has_text_or_watermark(img: Image.Image, edge_threshold: float = 0.085) -> bool:
    """Edge-density + OCR heuristic. Returns True if the image likely has text.

    Each check fails OPEN (an error means "don't reject"): in particular OCR is
    skipped silently when the Tesseract binary isn't installed, instead of
    rejecting every image.
    """
    try:
        gray = np.array(ImageOps.grayscale(img))
        edges = cv2.Canny(gray, 100, 200)
        if (np.sum(edges > 0) / edges.size) > edge_threshold:
            return True
    except Exception:
        pass
    if pytesseract is not None:
        try:
            txt = pytesseract.image_to_string(img.convert("L")).strip()
            if len([c for c in txt if c.isalnum()]) >= 4:
                return True
        except Exception:
            pass  # Tesseract binary missing / OCR failed -> just skip OCR
    return False


def _sharpness(img: Image.Image) -> float:
    try:
        return float(cv2.Laplacian(np.array(img.convert("L")), cv2.CV_64F).var())
    except Exception:
        return 0.0


def _saturation(img: Image.Image) -> float:
    try:
        arr = np.asarray(img.convert("RGB"), dtype="float32") / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        mx, mn = np.maximum.reduce([r, g, b]), np.minimum.reduce([r, g, b])
        return float(np.mean((mx - mn) / (mx + 1e-6)))
    except Exception:
        return 0.0


def _size_score(w: int, h: int) -> float:
    return math.log1p(w * h) / math.log1p(4000 * 4000)


def _normalize(vals: List[float]) -> List[float]:
    if not vals:
        return vals
    lo, hi = min(vals), max(vals)
    if hi <= lo + 1e-9:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def _pick_largest_from_srcset(srcset: str) -> Optional[str]:
    try:
        candidates = []
        for part in (p.strip() for p in srcset.split(",")):
            if " " in part:
                url, size = part.rsplit(" ", 1)
                try:
                    candidates.append((int(size.rstrip("w")), url))
                except ValueError:
                    candidates.append((0, url))
        if candidates:
            return sorted(candidates)[-1][1]
    except Exception:
        return None
    return None


# ===================== scraping core (sync) =====================

def _scrape_sync(query: str, limit: int, headless: bool) -> List[Dict]:
    raw: List[str] = []
    seen = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless, args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900}, user_agent=_BROWSER_UA
        )
        page = context.new_page()
        url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
        # domcontentloaded, not networkidle: Pinterest never goes idle and would hang 60s.
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:
            print(f"[scraper] goto warning: {exc}")
        page.wait_for_timeout(2500)
        for _ in range(6):
            page.mouse.wheel(0, random.randint(11000, 13000))
            page.wait_for_timeout(random.randint(900, 1400))
        for img in page.query_selector_all("img"):
            try:
                srcset = img.get_attribute("srcset")
                src = _pick_largest_from_srcset(srcset) if srcset else img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue
                src = _upgrade_pinimg_url(src)  # 60x60 thumb -> 736x full-res
                if src in seen:
                    continue
                seen.add(src)
                raw.append(src)
                if len(raw) >= limit * 5:
                    break
            except Exception:
                continue
        browser.close()

    processed: List[Dict] = []
    for src in raw:
        if len(processed) >= limit * 3:
            break
        try:
            img = Image.open(BytesIO(download_image_bytes(src))).convert("RGB")
            w, h = img.size
            if w < MIN_WIDTH or h < MIN_HEIGHT or _has_text_or_watermark(img):
                continue
            processed.append(
                {
                    "url": src,
                    "width": w,
                    "height": h,
                    "sharpness": _sharpness(img),
                    "saturation": _saturation(img),
                    "size_score": _size_score(w, h),
                }
            )
        except Exception:
            continue

    if not processed:
        return []

    sharp = _normalize([p["sharpness"] for p in processed])
    sat = _normalize([p["saturation"] for p in processed])
    size = _normalize([p["size_score"] for p in processed])
    for i, p in enumerate(processed):
        p["score"] = 0.55 * sharp[i] + 0.30 * sat[i] + 0.15 * size[i]
    processed.sort(key=lambda x: x["score"], reverse=True)
    return processed[:limit]


async def scrape_backgrounds(query: str, limit: int = DEFAULT_LIMIT, headless: bool = True) -> List[Dict]:
    """Async wrapper safe to call from FastAPI."""
    return await asyncio.to_thread(_scrape_sync, query, limit, headless)
