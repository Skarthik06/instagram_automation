# Affiliate Linker Agent

> Attaches a monetized affiliate link to every composed pin using Amazon SiteStripe,
> so each post actually earns commission. Falls back through progressively simpler
> methods so a link is always produced.

**Node:** `get_affiliate_links` · **Sources:** `graph/nodes.py`, `tools/amazon.py` · **Stage:** 6 of 8

---

## Mission

For each pin in `generated_content`, resolve an affiliate URL carrying the associate
tag and write it back into the pin's `affiliate_link` field.

## Inputs

- `state["generated_content"]` (from the Composer).
- `cfg.amazon.associate_tag`, `cfg.amazon.marketplace`.
- `amazon_page` (reuses the logged-in Amazon session).

## Outputs

- `generated_content` — same list, each item now with a populated `affiliate_link`.
- `stream_log`, and `errors` on failure.

## Tools & Capabilities

`get_affiliate_link(page, product, associate_tag, marketplace)` with a 3-tier
fallback:
1. **SiteStripe JSON API** (`getShortUrl`) — fastest when logged in.
2. **SiteStripe toolbar** — click the "Text" button, read the short-URL field.
3. **Manual tag URL** — `https://www.{marketplace}/dp/{asin}?tag={tag}` — always
   works.

## Rules & Constraints

- **R1 — The tag must always be present.** Correct monetization is the whole point;
  every returned link carries the associate tag. The tier-3 fallback guarantees a
  valid tagged URL even if SiteStripe is unavailable. (Revenue-critical)
- **R2 — Resolve the ASIN safely.** Prefer `product["asin"]`; else extract from the
  URL via `_extract_asin`. No ASIN and no URL → return the product URL unchanged and
  warn (rare; upstream requires an ASIN).
- **R3 — Gentle pacing.** `await asyncio.sleep(1.5)` between products — do not hammer
  Amazon. (Global G4)
- **R4 — Never raise.** Exceptions → `{"errors": [...]}`; downstream handles missing
  links defensively. (Global G1)
- **R5 — Preserve pin content.** Only the `affiliate_link` field is added; titles,
  descriptions, hashtags, and the product are passed through untouched (including the
  FTC disclosure — G3).
- **R6 — No `generated_content` is an error.** If the list is empty, record an error
  and produce nothing (shouldn't happen after the `_has_content` gate).

## Failure Handling

- SiteStripe API 4xx/5xx → silently fall through to the toolbar, then the manual tag
  URL. The tiered design means a "failure" degrades link quality, not link presence.
- Full node exception → error recorded; the Publisher still runs but may post links
  lacking a short URL.

## Done / Success Criteria

Every pin in `generated_content` has a non-empty `affiliate_link` containing the
associate tag (short URL preferred, manual tagged URL acceptable).

## Notes

SiteStripe short URLs are cleaner and more trusted on Pinterest, but the manual
`?tag=` fallback is functionally equivalent for attribution — so the agent optimizes
for "always monetized" over "always pretty".
