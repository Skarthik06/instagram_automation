# Agent — Product Scout (retrieval + category taxonomy)

**Role:** The retrieval brain. Given one or more categories, decide **what to search on
Amazon India and which products to keep** so the user receives products worth stopping
the scroll for — not "a list of Amazon links". This agent governs *how products are
extracted per category*.

**Code anchors:** `tools/amazon.py` (`scrape_products`, `_passes_quality`, `_SCRAPE_JS`),
`server.py` (`CATEGORY_RATES`, `/api/generate`, `_resolve_categories`), `config.py`
(`BotConfig` quality constraints). Legend: ✓ = already enforced in code · ⏳ = pending code wiring.

---

## S1 — The five-question gate (MOST IMPORTANT decision logic)
Before a product is offered to the user it must plausibly pass ALL five. A product that
fails Q1–Q3 is dropped; one that fails Q4–Q5 is deprioritised, not featured.
1. Would someone **stop scrolling** for this? (visual pull)
2. Would someone **click** it?
3. Would someone **actually consider buying** it? (real need/want + accessible price)
4. Can it create **multiple pieces of content**? (angles — see [[content-strategist]])
5. Can it be grouped into an **attractive collection/bundle**? (see [[collection-builder]])
Only AFTER these may affiliate commission influence ranking. Commission never dominates.

## S2 — Category taxonomy (families → subcategories → search intent)
Retrieval is organised as **families**. Each family owns subcategories; each subcategory
maps to concrete Amazon India search terms. The current 8 config categories
(`fashion, home, kitchen, beauty, fitness, toys, books, electronics`) are the backward-
compatible base; the families below are the target taxonomy (⏳ extend `VALID_CATEGORIES`
+ a `SUBCATEGORIES` map; keep the 8 as aliases so existing calls keep working).

| Family | Maps to base | Representative subcategories (search intent) |
|--------|--------------|-----------------------------------------------|
| **fashion** | fashion | oversized/graphic tees, shirts, hoodies, jackets, cargos, baggy/straight jeans, co-ords, ethnic; women: tops, dresses, kurtis, co-ords, bags; footwear: sneakers, slides, loafers; accessories: watches, sunglasses, wallets, belts, caps, backpacks |
| **tech** | electronics | wireless headphones, TWS earbuds, BT speakers, neckbands, smartwatches, fast chargers, power banks, cables, phone/laptop stands, keyboards, mice, webcams, mics, USB hubs, LED strips |
| **room_desk** | home | LED/RGB lights, desk lamps, monitor lights, desk mats, organizers, cable management, shelves, posters, artificial plants, clocks, minimalist décor |
| **everyday** | home/kitchen | kitchen gadgets, storage, cleaning gadgets, organization, car/bathroom organizers, cable management, multi-purpose EDC |
| **fitness** | fitness | resistance bands, yoga mats, gym bags, water bottles, shakers, skipping ropes, running/cycling accessories |
| **student** | electronics/home | backpacks, laptop sleeves, study lamps, organizers, bottles, budget earphones, power banks, phone stands, stationery |
| **travel** | home | travel bags, packing cubes, toiletry organizers, adapters, neck pillows, luggage accessories |
| **gifting** | fashion/home | watches, wallets, bags, desk accessories, gadgets, décor, lifestyle |
| **beauty** | beauty | grooming accessories, hair accessories, makeup organizers, mirrors, storage (accessories only — NOT ingestible/health) |
| **gaming** | electronics | gaming mice/keyboards, mousepads, headsets, controllers, RGB, stands, cable mgmt, mics, webcams |

Rule: a retrieval request names a family (or a base category); the scout expands it to
subcategory search terms and runs the existing search-results scrape per term.

## S3 — Quality filter (reject / deprioritise) ✓ partly enforced
Drop or heavily deprioritise a product when: rating very poor · info incomplete (no
price or image) · price outside the impulse band · weak visual appeal · no obvious
consumer benefit · unattractive price/value · listing looks unreliable (sponsored-only,
no reviews) · category unsuitable · data stale · unavailable.
Already enforced by `_passes_quality` (price+image required, price band, min rating, min
reviews). ⏳ Add: image-quality/visual-appeal signal, "explainability" flag, staleness check.
**Never** promote a product just because it is an Amazon bestseller (S1 still applies).

## S4 — No fabrication (hard rule) ✓ enforced by construction
Preserve the actual data the source returned. NEVER invent price, discount, rating,
reviews, specs, availability, images, affiliate URLs, or trend claims. If a field is
unavailable, mark it unavailable — do not guess. Affiliate URLs are built only from the
real ASIN + the configured tag (`sparkle060b-21`); ordinary URLs are never silently
"converted". See [[content-strategist]] S-rules on claim safety.

## S5 — Multi-retailer product model (future-ready) ⏳
Every product record must be able to carry: `retailer, product_id, product_url,
affiliate_url, title, description, image, price, original_price, discount, rating,
category, subcategory, content_score, instagram_score, purchase_intent_score,
value_score, content_potential_score, availability, last_updated`, plus a
`product_type ∈ {AFFILIATE_PRODUCT, STORE_PRODUCT}`. Current source = `retailer:"amazon_in"`,
`product_type:"AFFILIATE_PRODUCT"`. An affiliate product must NEVER be presented as owned
inventory. Do not build unsupported retailer integrations speculatively.

## S6 — Freshness ✓ partly (sk_posts timestamps) ⏳ extend
Track `last_checked`, `last_price_update`, `availability`. Stale products lose ranking
priority; unavailable products are removed/deprioritised. Never present stale data as current.

## S7 — Handoff
Scout emits validated, deduped candidates (dedup via [[dedup-guard]]) grouped by
category/subcategory, each carrying raw grounded fields, to [[product-scorer]] for scoring
and tiering. Scout does not write content or post.
