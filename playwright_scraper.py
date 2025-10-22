# playwright_scraper.py
import asyncio
from playwright.async_api import async_playwright
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
    """Estimate sharpness using variance of Laplacian (OpenCV)."""
    try:
        img_gray = np.array(img_pil.convert("L"))
        lap = cv2.Laplacian(img_gray, cv2.CV_64F)
        var = float(lap.var())
        return var
    except Exception:
        return 0.0


def _mean_saturation(img_pil):
    try:
        img = img_pil.convert("RGB")
        arr = np.array(img).astype("float32") / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        # avoid division by zero
        denom = (maxc + 1e-6)
        sat = (maxc - minc) / denom
        return float(np.mean(sat))
    except Exception:
        return 0.0


def _size_score(w, h):
    # prefer larger images; normalize roughly to 0-1 with a soft cap
    area = w * h
    # use log scale to avoid huge differences
    return math.log1p(area) / math.log1p(4000 * 4000)


def _normalize(vals):
    if not vals:
        return vals
    mn = min(vals)
    mx = max(vals)
    if mx <= mn + 1e-9:
        return [0.5 for _ in vals]
    return [(v - mn) / (mx - mn) for v in vals]


async def scrape_pinterest_images(prompt, limit=DEFAULT_LIMIT, existing_urls=None, headless=True):
    """
    Scrape Pinterest search results for `prompt`.
    Returns a ranked list of dicts:
      [{"url": ..., "alt": ..., "width": w, "height": h, "score": s}, ...]
    The list length will be <= limit.
    """
    if existing_urls is None:
        existing_urls = set()
    else:
        existing_urls = set(existing_urls)

    candidates = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1400, "height": 900})
        search_url = f"https://www.pinterest.com/search/pins/?q={prompt.replace(' ', '%20')}"
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        # scroll with some randomization
        for _ in range(6):
            await page.mouse.wheel(0, random.randint(11000, 13000))
            await asyncio.sleep(random.uniform(1.0, 1.5))

        img_elements = await page.query_selector_all("img")
        # collect raw candidate metadata first (avoid downloading too many)
        for img in img_elements:
            try:
                srcset = await img.get_attribute("srcset")
                src = _pick_largest_from_srcset(srcset) if srcset else await img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue
                if is_duplicate_image_url(src, existing_urls):
                    continue
                alt = (await img.get_attribute("alt")) or ""
                candidates.append({"url": src, "alt": alt})
                if len(candidates) >= limit * 4:  # fetch a few more to allow filtering
                    break
            except Exception:
                continue

        # download and validate images, compute visual features
        processed = []
        for c in candidates:
            if len(processed) >= limit * 3:
                break
            src = c["url"]
            try:
                b = download_image_bytes(src, timeout=REQUEST_TIMEOUT)
                img_obj = Image.open(BytesIO(b)).convert("RGB")
                w, h = img_obj.size
                if w < MIN_WIDTH or h < MIN_HEIGHT:
                    continue
                if has_watermark(img_obj):
                    continue
                sharp = _sharpness_cv2(img_obj)
                sat = _mean_saturation(img_obj)
                ssize = _size_score(w, h)
                processed.append({
                    "url": src,
                    "alt": c.get("alt", ""),
                    "width": w,
                    "height": h,
                    "sharpness": sharp,
                    "saturation": sat,
                    "size_score": ssize
                })
            except Exception:
                continue

        await browser.close()

    if not processed:
        return []

    # normalize features
    sharp_vals = [p["sharpness"] for p in processed]
    sat_vals = [p["saturation"] for p in processed]
    size_vals = [p["size_score"] for p in processed]

    sharp_n = _normalize(sharp_vals)
    sat_n = _normalize(sat_vals)
    size_n = _normalize(size_vals)

    # combine into a single relevance score (weights chosen empirically)
    ranked = []
    for i, p in enumerate(processed):
        score = 0.55 * sharp_n[i] + 0.30 * sat_n[i] + 0.15 * size_n[i]
        ranked.append({**p, "score": score})

    # sort descending by score and return top `limit`
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]
