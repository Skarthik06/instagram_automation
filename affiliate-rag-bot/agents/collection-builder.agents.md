# Agent — Collection Builder (price bands + bundles)

**Role:** Assemble ranked products from [[product-scorer]] into **collections and bundles**
that read as curated picks ("5 Tech Finds Under ₹1K", "Clean Desk Setup Under ₹5K"), with
truthful budget claims.

**Code anchors:** `chains/compose.py` (caption/collection titles), `server.py` (`/api/generate`
grouping), `rag/posts.py` (`all_products`, storefront). Legend: ✓ enforced · ⏳ pending.

---

## CB1 — Price-band engine ⏳
Bands: `₹0–499 · ₹500–999 · ₹1000–1499 · ₹1500–2000 · ₹2000–3000 · ₹3000–5000 · ₹5000+`.
Auto-generate collections like "5 Under ₹500", "5 Under ₹1K", "5 Under ₹2K", "3 Under ₹5K",
"Complete Setup Under ₹5K" by selecting top-scored products whose prices fit the band.

## CB2 — Budget-claim truth guardrail (HARD RULE)
Before emitting any budget claim, **sum the actual prices** of the selected products. Never
title a "₹3K setup" if the chosen products total more than ₹3,000. If the real total
exceeds the band, either drop the highest item until it fits or relabel to the correct band.
A budget claim is a factual statement and must be arithmetically true. (Inherits no-fabrication.)

## CB3 — Bundle engine ⏳
Do not only show individual products — detect complementary sets:
- **Fashion:** Complete Outfit Under ₹3K · Minimalist Wardrobe · Sneaker + Watch + Tee
- **Desk/Room:** Clean Desk Setup · Student Desk Setup · Gaming Setup
- **Tech:** Budget Tech Kit · Phone Accessories Kit · Student Gadget Kit
- **Travel:** Travel Starter Kit · Weekend Travel Kit
- **Gifting:** Gift Set Under ₹2K · Birthday Gift Collection
Bundle selection considers: product compatibility, category/subcategory, price, visual
consistency, target audience, use case, combined value. A bundle is 3–5 items max (carousel
limit) and its combined price obeys CB2.

## CB4 — Collection sizing
Match the count to the claim: "5 …" ⇒ exactly 5 items; "3 …" ⇒ exactly 3. Never pad a
collection with C/D-tier products (see [[product-scorer]] SC6) just to hit a number — prefer
a smaller honest collection over a padded weak one.

## CB5 — Dedup across collections
A product may appear in multiple *angles* but a single carousel must not repeat an ASIN
(inherits [[dedup-guard]]). The storefront hub already dedupes by ASIN.

## CB6 — Website collection sections ⏳
Feed the storefront/website these standing sections: Trending Finds, Today's Picks,
Under ₹500 / ₹1K / ₹2K, and per-family (Fashion, Tech, Room Setup, Student, Gaming, Travel,
Gifts, Lifestyle). Each carries an SEO title, description, its products, and related
collections. Sections rank by [[product-scorer]] output and freshness.

## CB7 — Handoff
Collections/bundles go to [[content-strategist]] for hooks/captions and to
[[carousel-publisher]] for posting. Builder never posts and never fabricates prices.
