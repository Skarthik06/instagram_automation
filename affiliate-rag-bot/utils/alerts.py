"""
utils/alerts.py  —  Safe, resilient selector finder.

Tries an ordered list of CSS selectors and returns the first element that
resolves. When every selector fails (usually because Amazon/Pinterest changed
their UI), it logs a clear warning so the failure is visible in the run log and
the JSON `errors` output.

(Email alerting was removed — failures now surface through the structured run
log/errors instead of SMTP.)
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page, ElementHandle

from utils.logger import log


async def find_element(
    page: "Page",
    selectors: list[str],
    context: str,
) -> Optional["ElementHandle"]:
    """
    Try each selector in order and return the first element that resolves.
    If none resolve, log a warning (with the context + tried selectors) and
    return None. Drop-in replacement for a bare page.query_selector() call.
    """
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                return el
        except Exception:
            continue  # bad selector syntax — try next

    # All selectors failed — surface it loudly in the run log.
    log.warning(
        f"[selector-miss] {context} — none of {len(selectors)} selectors matched: "
        f"{selectors} @ {getattr(page, 'url', '')}"
    )
    return None
