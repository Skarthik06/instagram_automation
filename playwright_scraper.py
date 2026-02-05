# playwright_scraper.py
import asyncio
from playwright.sync_api import sync_playwright
from utils.filters import download_image_bytes, has_watermark, is_duplicate_image_url
from PIL import Image
from io import BytesIO
import random
import cv2
import numpy as np
import math

DEFAULT_LIMIT = 12
MIN_WIDTH = 800
MIN_HEIGHT = 800
REQUEST_TIMEOUT = 8


def _pick_largest_from_srcset(srcset: str):
    try:
        parts = [p.strip() for p in srcset.split(",")]
        candidates = []
        for p in parts:
            if " " in p:
                url, size = p.rsplit(" ", 1)
                try:
                    w = int(size.rstrip("w"))
                except:
                    w = 0
                candidates.append((w, url))
        if candidates:
            candidates.sort()
            return candidates[-1][1]
    except Exception:
        return None
    return None


def _sharpness_cv2(img_pil):
    try:
        img_gray = np.array(img_pil.convert("L"))
        lap = cv2.Laplacian(img_gray, cv2.CV_64F)
        return float(lap.var())
    except Exception:
        return 0.0


def _mean_saturation(img_pil):
    try:
        arr = np.array(img_pil.convert("RGB")).astype("float32") / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        maxc = np.maximum.reduce([r, g, b])
        minc = np.minimum.reduce([r, g, b])
        sat = (maxc - minc) / (maxc + 1e-6)
        return float(np.mean(sat))
    except Exception:
        return 0.0


def _size_score(w, h):
    area = w * h
    return math.log1p(area) / math.log1p(4000 * 4000)


def _normalize(vals):
    if not vals:
        return vals
    mn, mx = min(vals), max(vals)
    if mx <= mn + 1e-9:
        return [0.5] * len(vals)
    return [(v - mn) / (mx - mn) for v in vals]


# ===================== SYNC SCRAPER CORE =====================

def _scrape_sync(prompt, limit, existing_urls, headless):
    candidates = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})

        search_url = f"https://www.pinterest.com/search/pins/?q={prompt.replace(' ', '%20')}"
        page.goto(search_url, wait_until="networkidle", timeout=60000)

        page.wait_for_timeout(2000)

        for _ in range(6):
            page.mouse.wheel(0, random.randint(11000, 13000))
            page.wait_for_timeout(random.randint(1000, 1500))

        img_elements = page.query_selector_all("img")

        for img in img_elements:
            try:
                srcset = img.get_attribute("srcset")
                src = _pick_largest_from_srcset(srcset) if srcset else img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue
                if is_duplicate_image_url(src, existing_urls):
                    continue
                alt = img.get_attribute("alt") or ""
                candidates.append({"url": src, "alt": alt})
                if len(candidates) >= limit * 4:
                    break
            except Exception:
                continue

        browser.close()

    processed = []
    for c in candidates:
        if len(processed) >= limit * 3:
            break
        try:
            b = download_image_bytes(c["url"], timeout=REQUEST_TIMEOUT)
            img_obj = Image.open(BytesIO(b)).convert("RGB")
            w, h = img_obj.size
            if w < MIN_WIDTH or h < MIN_HEIGHT:
                continue
            if has_watermark(img_obj):
                continue

            processed.append({
                "url": c["url"],
                "alt": c["alt"],
                "width": w,
                "height": h,
                "sharpness": _sharpness_cv2(img_obj),
                "saturation": _mean_saturation(img_obj),
                "size_score": _size_score(w, h)
            })
        except Exception:
            continue

    if not processed:
        return []

    sharp_n = _normalize([p["sharpness"] for p in processed])
    sat_n = _normalize([p["saturation"] for p in processed])
    size_n = _normalize([p["size_score"] for p in processed])

    ranked = []
    for i, p in enumerate(processed):
        score = 0.55 * sharp_n[i] + 0.30 * sat_n[i] + 0.15 * size_n[i]
        ranked.append({**p, "score": score})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


# ===================== ASYNC WRAPPER (FASTAPI SAFE) =====================

async def scrape_pinterest_images(prompt, limit=DEFAULT_LIMIT, existing_urls=None, headless=True):
    if existing_urls is None:
        existing_urls = set()
    else:
        existing_urls = set(existing_urls)

    return await asyncio.to_thread(
        _scrape_sync,
        prompt,
        limit,
        existing_urls,
        headless
    )
