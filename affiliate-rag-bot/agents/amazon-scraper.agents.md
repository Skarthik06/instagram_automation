# Amazon Scraper Agent

> Logs into Amazon and scrapes the Best Sellers grid for the requested category,
> producing the raw product candidate list that seeds the whole pipeline.

**Node:** `scrape_amazon` · **Sources:** `graph/nodes.py`, `tools/amazon.py` · **Stage:** 1 of 8

---

## Mission

Return up to ~25 real, buyable products (title, price, image, URL, ASIN, rating) from
the Amazon India Best Sellers page for `state["category"]`. This is the top of the
funnel — if it returns nothing, the run aborts.

## Inputs (reads from state / config)

- `state["category"]` — category slug (mapped via `CATEGORY_SLUGS`).
- `cfg.amazon.{email, password, marketplace}` — credentials + marketplace host.
- `amazon_page` — the Playwright page from `config.configurable`.

## Outputs (writes to state)

- `raw_products: list[ProductData]` — scraped candidates (may contain dupes).
- `stream_log` — one human-readable progress line.
- `errors` — on failure only.

## Tools & Capabilities

- `amazon_login(page, email, password, marketplace)` — idempotent: detects an
  existing session and skips re-login.
- `scrape_best_sellers(page, category, marketplace)` — navigates the bestsellers
  slug, triggers lazy-load by scrolling, and extracts items in-page via a resilient
  multi-selector `page.evaluate`.

## Rules & Constraints

- **R1 — Stealthy, human-paced login.** Type credentials with `_human_type`
  (randomized per-key delay) and randomized navigation pauses. Reuse an existing
  session when detected. (Global G4)
- **R2 — Resilient extraction.** Try each selector group in order until ≥5 items
  match; keep only rows with a real title (`> 3` chars) **and** an ASIN. A missing
  ASIN row is discarded, not guessed.
- **R3 — Empty result is a handled outcome, not a crash.** If zero products, return
  `{"errors": ["... no products found — Amazon DOM may have changed"]}` — the
  Orchestrator's `_has_raw` gate then aborts the run. (Global G1, G2 fail-closed)
- **R4 — Never raise.** Any exception → `{"raw_products": [], "errors": [...]}`.
- **R5 — Cap the candidate set.** Take at most the first 25 items; downstream token
  discipline depends on a bounded list.
- **R6 — Marketplace-correct URLs.** Relative hrefs are absolutized against
  `https://www.{marketplace}`. Do not hardcode `.com`.

## Failure Handling

- DOM/selector drift → empty `raw_products` + error string → clean abort. Consider
  wiring `utils.alerts.find_element` here so selector drift logs a `[selector-miss]`
  warning into the run log. (G11)
- Login challenge / OTP → surfaces as an exception captured in `errors`; the run
  aborts rather than hanging.

## Done / Success Criteria

`raw_products` is a non-empty list of dicts each having a non-empty `title` and a
10-char `asin`. A `stream_log` line reports the count scraped.

## Notes

`CATEGORY_SLUGS` maps friendly categories to Amazon bestseller slugs; unknown
categories fall back to the generic `bestsellers` grid.
