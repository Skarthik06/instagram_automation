# playwright_scraper.py
import asyncio
from playwright.async_api import async_playwright
from utils.filters import download_image_bytes, has_watermark, is_duplicate_image_url
from PIL import Image
from io import BytesIO
import time

DEFAULT_LIMIT = 5
MIN_WIDTH = 320
MIN_HEIGHT = 320
REQUEST_TIMEOUT = 6

def _pick_largest_from_srcset(srcset: str):
    # srcset format: "url1 236w, url2 564w, url3 1000w"
    try:
        parts = [p.strip() for p in srcset.split(",")]
        candidates = []
        for p in parts:
            if " " in p:
                url, size = p.rsplit(" ", 1)
                # size like '1000w' -> numeric
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
    """
    Return a list of public image URLs (strings).
    - prompt: dynamic Pinterest search prompt (string)
    - limit: return up to N URLs
    - existing_urls: iterable of already-used image URLs to avoid duplicates
    """
    if existing_urls is None:
        existing_urls = set()
    else:
        existing_urls = set(existing_urls)

    found = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        # set viewport and user-agent for more consistent results
        await page.set_viewport_size({"width": 1200, "height": 800})
        # navigate to search
        search_url = f"https://www.pinterest.com/search/pins/?q={prompt.replace(' ', '%20')}"
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        # allow dynamic content to load
        await asyncio.sleep(2)

        # scroll to load images
        for _ in range(4):
            await page.mouse.wheel(0, 10000)
            await asyncio.sleep(1.2)

        img_elements = await page.query_selector_all("img")
        for img in img_elements:
            if len(found) >= limit:
                break
            try:
                srcset = await img.get_attribute("srcset")
                src = None
                if srcset:
                    src = _pick_largest_from_srcset(srcset)
                if not src:
                    src = await img.get_attribute("src")
                if not src or not src.startswith("http"):
                    continue
                # skip duplicates by URL
                if is_duplicate_image_url(src, existing_urls):
                    continue
                # quick fetch and validate image
                try:
                    b = download_image_bytes(src, timeout=REQUEST_TIMEOUT)
                    img_obj = Image.open(BytesIO(b)).convert("RGB")
                    w, h = img_obj.size
                    if w < MIN_WIDTH or h < MIN_HEIGHT:
                        continue
                    # watermark/text check (optional heavy) - if True => skip
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
