# Agent — Product Scorer (multi-score ranking + tiers)

**Role:** Turn grounded candidates from [[product-scout]] into ranked, tiered products
using several **configurable 0–100 scores**, so ranking rewards scroll-stopping,
buy-worthy, content-rich products — not raw commission.

**Code anchors:** `tools/amazon.py` (`_attractiveness` — the current single score),
`config.py` (weights/thresholds live here), `chains/compose.py` (LLM ranking pass).
Legend: ✓ enforced · ⏳ pending code wiring. All weights/thresholds MUST be config-driven.

---

## SC1 — Product Content Score (0–100) — the master score ⏳
Weighted blend (initial weights, all configurable in `config.py`):
| Weight | Dimension | Evaluate |
|-------:|-----------|----------|
| 30% | **Instagram / visual appeal** | photography, visual quality, scroll-stop, aesthetic, "wow", demo / before-after / transformation potential |
| 20% | **Purchase intent** | obvious reason to buy, solves a problem, actively wanted, understandable, accessible price |
| 15% | **Price / value** | current price, value-for-money, reliable discount, quality-to-price, brand perception |
| 15% | **Content potential** | how many distinct content angles it supports (see [[content-strategist]]) |
| 10% | **Quality / social proof** | rating, review count, brand reputation, info completeness |
| 10% | **Affiliate / commercial** | commercial value — but MUST NOT dominate ranking |
The existing `_attractiveness` (rating·20 + log reviews·10 + discount·0.4 + log demand·8 +
badge) is a good **Quality/social-proof + value** proxy; keep it as the deterministic core
and fold it into the 10%+15% bands. The visual/intent/content bands are new (⏳).

## SC2 — Instagram Score (0–100) ⏳
Separate from purchase intent. Evaluate visual appeal, hook potential, shareability, save
potential, relatability, demonstration/transformation potential, trend relevance, aesthetic.
A product can have HIGH purchase intent and LOW Instagram appeal — the system must record
both independently and not conflate them.

## SC3 — Purchase Intent Score (0–100) ⏳
Evaluate clear problem solved, need/want strength, price accessibility, usefulness, search
intent (where data exists), social proof, practicality, giftability, repeat-use potential.

## SC4 — Value Score (0–100) ✓ core exists ⏳ formalise
Use ONLY reliable data: current price, reference price when available, discount only when
reliably calculated, rating, review volume, features, brand, price-to-value. NEVER assert
"lowest price ever", "biggest discount", or a specific "% OFF" unless the scraped data
supports it exactly (`discount_pct` from the listing). See [[content-strategist]] SG1.

## SC5 — Content Potential Score (0–100) ⏳
How many distinct Instagram/content concepts the product supports (e.g. a headphone →
"best under ₹5K", "student gadgets", "travel gadgets", "tech finds", "gift ideas",
"JBL vs Sony", "budget audio setup"). More viable angles ⇒ higher score.

## SC6 — Priority tiers (configurable thresholds) ⏳
From the Product Content Score:
`S 90–100` exceptional · `A 80–89` strong · `B 70–79` good · `C 60–69` keep, low priority ·
`D <60` do not prominently feature. Thresholds live in `config.py`. Carousels and the
storefront feature S/A first; C/D are held back or used only to fill collections.

## SC7 — Ranking rule
Sort candidates by Product Content Score desc, breaking ties by Value then Instagram
score. The final selection handed to [[carousel-publisher]] and [[collection-builder]] is
the top-N per category by this order — NOT by commission and NOT raw bestseller rank.

## SC8 — Learning hook (future) ⏳
Scores are priors, not permanent truth. When real performance data exists (see analytics),
adjust family/price-band/hook priority from actual clicks/saves/visits. Do not hard-code
"fashion always wins" — let measured performance reweight. Persist learned weights in config
or the DB, never inline in logic.

## SC9 — Honesty
Every score is derived from real fields or explicit heuristics; a score is never a claim
about the product shown to buyers. Scores rank internally — they are not printed as
"98/100 amazing!" marketing. No fabrication (inherits [[product-scout]] S4).
