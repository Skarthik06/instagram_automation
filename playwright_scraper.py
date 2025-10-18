# playwright_scraper.py
import asyncio
from playwright.async_api import async_playwright
from utils.filters import download_image_bytes, has_watermark, is_duplicate_image_url
from PIL import Image
from io import BytesIO
import random

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

async def scrape_pinterest_images(prompt, limit=DEFAULT_LIMIT, existing_urls=None, headless=True):
    if existing_urls is None:
        existing_urls = set()
    else:
        existing_urls = set(existing_urls)

    found = []
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
        for img in img_elements:
            if len(found) >= limit:
                break
            try:
                srcset = await img.get_attribute("srcset")
                src = _pick_largest_from_srcset(srcset) if srcset else await img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue
                if is_duplicate_image_url(src, existing_urls):
                    continue
                try:
                    b = download_image_bytes(src, timeout=REQUEST_TIMEOUT)
                    img_obj = Image.open(BytesIO(b)).convert("RGB")
                    w, h = img_obj.size
                    if w < MIN_WIDTH or h < MIN_HEIGHT:
                        continue
                    if has_watermark(img_obj):
                        continue
                    found.append(src)
                    existing_urls.add(src)
                except Exception:
                    continue
            except Exception:
                continue
        await browser.close()
    return found
