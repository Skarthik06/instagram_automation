"""
tools/pinterest.py  —  Async Playwright Pinterest automation.

Handles: login, board creation, pin posting with human-like typing.
"""
from __future__ import annotations
import asyncio
import random
import tempfile
import os
from pathlib import Path

import httpx
from playwright.async_api import Page

from utils.logger import log
from utils.alerts import find_element


async def _delay(min_ms: int, max_ms: int = 0) -> None:
    ms = random.randint(min_ms, max_ms or min_ms)
    await asyncio.sleep(ms / 1000)


async def _human_type(page: Page, selector: str, text: str) -> None:
    """Simulate human typing cadence — anti-bot detection bypass."""
    await page.click(selector)
    await _delay(200, 400)
    for char in text:
        await page.type(selector, char, delay=random.randint(35, 115))
    await _delay(100, 200)


async def _download_image(url: str) -> str | None:
    """Download product image to a temp file. Returns local path."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
        suffix = ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(r.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        log.warning(f"Image download failed: {e}")
        return None


# ─── Login ───────────────────────────────────────────────────────────────────

async def pinterest_login(page: Page, email: str, password: str) -> None:
    log.step("Logging into Pinterest...")
    await page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")
    await _delay(2000, 3000)

    # Already logged in?
    avatar = await page.query_selector('[data-test-id="header-avatar"]')
    if avatar:
        log.success("Already logged into Pinterest ✓")
        return

    await _human_type(page, "#email",    email)
    await _delay(400, 700)
    await _human_type(page, "#password", password)
    await _delay(500, 900)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("domcontentloaded")
    await _delay(3000, 5000)

    # Dismiss popups
    close = await page.query_selector('[data-test-id="modal-close-button"], [aria-label="Close"]')
    if close:
        await close.click()

    log.success("Logged into Pinterest ✓")


# ─── Board ───────────────────────────────────────────────────────────────────

async def ensure_board_exists(page: Page, board_name: str) -> None:
    log.step(f'Checking board: "{board_name}"...')
    await page.goto("https://www.pinterest.com/me/boards/", wait_until="domcontentloaded")
    await _delay(2000, 3000)

    exists = await page.evaluate(
        """(name) => {
            const els = Array.from(document.querySelectorAll('[data-test-id="board-name"], h2, h3'));
            return els.some(el => el.textContent.trim().toLowerCase() === name.toLowerCase());
        }""",
        board_name,
    )

    if exists:
        log.success(f'Board "{board_name}" already exists ✓')
        return

    log.step(f'Creating board: "{board_name}"...')
    await page.goto("https://www.pinterest.com/board-create/", wait_until="domcontentloaded")
    await _delay(2000)

    inp = await find_element(
        page,
        ['input[id="boardName"]', '[data-test-id="board-name-input"] input'],
        "Pinterest board create: name input",
    )
    if inp:
        await _human_type(page, 'input[id="boardName"]', board_name)
        await _delay(400)
        btn = await page.query_selector('button[type="submit"], [data-test-id="board-create-button"]')
        if btn:
            await btn.click()
            await _delay(3000)
            log.success(f'Board "{board_name}" created ✓')


# ─── Create Pin ──────────────────────────────────────────────────────────────

async def create_pin(
    page:           Page,
    product:        dict,
    pin_title:      str,
    pin_description: str,
    hashtags:       list[str],
    affiliate_link: str,
    board_name:     str,
) -> bool:
    log.step(f"Creating pin: {pin_title[:50]}...")

    # Download image
    image_path = await _download_image(product.get("image", ""))

    # Navigate to Pin Builder
    await page.goto("https://www.pinterest.com/pin-builder/", wait_until="domcontentloaded")
    await _delay(3000, 4500)

    # ── Upload image ──────────────────────────────────────────────────
    if image_path and os.path.exists(image_path):
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            await file_input.set_input_files(image_path)
            await _delay(3000, 5000)
            log.info("Image uploaded ✓")

    # ── Title ─────────────────────────────────────────────────────────
    title_el = await find_element(
        page,
        ['[data-test-id="pin-draft-title"] textarea', '[placeholder*="title" i]', 'textarea[name="title"]'],
        "Pinterest pin builder: title field",
    )
    if title_el:
        await _human_type(page, '[data-test-id="pin-draft-title"] textarea', pin_title)
        log.info("Title typed ✓")
    await _delay(500, 800)

    # ── Description ───────────────────────────────────────────────────
    full_desc = f"{pin_description}\n\n{' '.join('#' + h for h in hashtags)}"
    desc_el = await find_element(
        page,
        ['[data-test-id="pin-draft-description"] textarea', '[placeholder*="description" i]', 'textarea[name="description"]'],
        "Pinterest pin builder: description field",
    )
    if desc_el:
        await _human_type(page, '[data-test-id="pin-draft-description"] textarea', full_desc[:500])
        log.info("Description typed ✓")
    await _delay(500, 800)

    # ── Affiliate link ─────────────────────────────────────────────────
    link_el = await find_element(
        page,
        ['[data-test-id="pin-draft-link"] input', '[placeholder*="destination" i]', '[placeholder*="link" i]', 'input[name="link"]'],
        "Pinterest pin builder: destination link field",
    )
    if link_el:
        await _delay(300, 500)
        await _human_type(page, '[data-test-id="pin-draft-link"] input', affiliate_link)
        log.info("Affiliate link typed ✓")
    await _delay(800, 1200)

    # ── Board selector ────────────────────────────────────────────────
    board_btn = await find_element(
        page,
        ['[data-test-id="board-dropdown-select-button"]', 'button[aria-haspopup="listbox"]'],
        "Pinterest pin builder: board selector",
    )
    if board_btn:
        await board_btn.click()
        await _delay(1000, 1500)

        search_inp = await page.query_selector('[data-test-id="board-search-input"] input, input[placeholder*="Search" i]')
        if search_inp:
            await _human_type(page, '[data-test-id="board-search-input"] input', board_name)
            await _delay(800, 1200)

        clicked = await page.evaluate(
            """(name) => {
                const opts = Array.from(document.querySelectorAll('[data-test-id="board-row"], li[role="option"]'));
                const match = opts.find(el => el.textContent.toLowerCase().includes(name.toLowerCase()));
                if (match) { match.click(); return true; }
                return false;
            }""",
            board_name,
        )
        if clicked:
            log.info(f'Board "{board_name}" selected ✓')

    await _delay(1000, 1500)

    # ── Publish ───────────────────────────────────────────────────────
    published = False
    for sel in [
        '[data-test-id="board-dropdown-publish-button"]',
        'button[data-test-id="pin-draft-publish-button"]',
        'button[type="submit"]',
    ]:
        btn = await page.query_selector(sel)
        if btn:
            txt = (await btn.text_content() or "").lower()
            if "publish" in txt or "save" in txt:
                await btn.click()
                await _delay(3000, 5000)
                log.success(f"✅ Pin published: {pin_title}")
                published = True
                break

    # Cleanup temp image
    if image_path and os.path.exists(image_path):
        os.unlink(image_path)

    return published
