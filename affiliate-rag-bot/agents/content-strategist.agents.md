# Agent — Content Strategist (hooks, descriptions, CTAs, formats)

**Role:** For high-scoring products/collections, generate the **content layer** — reel
hooks, descriptions, carousel titles, CTAs — grounded strictly on real data.

**Code anchors:** `chains/compose.py` (the ONE LLM call that writes captions/hooks/hashtags),
`server.py` `/api/generate` (returns `summary`, `hashtags`, etc.). Legend: ✓ · ⏳.

---

## CG1 — ONE category caption per carousel: scannable, bold, clean (token-efficient) ✓ enforced
The single LLM call writes exactly ONE caption + one hashtag set for the WHOLE carousel —
NOT one per product (`chains/compose.PinBatch` = `{picks, caption, hashtags}`). All picks share
this one caption: saves tokens (one, not N) and matches Instagram (one caption per carousel).
It MUST follow every rule below (enforced by the prompt + post-processing in `chains/compose.py`):

**Structure — SHORT and SKIMMABLE (people don't read paragraphs), with real line breaks:**
1. Emoji-led HOOK line themed on the CATEGORY — e.g. `🍔👕 Graphic Tees under ₹1K!`
2. `🔥 Top picks you can't miss:`
3. ONE LINE PER PRODUCT (each on its own new line, up to 5): `- <Brand/short name> — ₹<price> (<X>% off)`.
   **Lead with the BRAND name**, popular brands especially.
4. ONE short "why they're worth it" line.
5. CTA: `🛒 Shop all via the link in bio 👆`

**Bold the money bits (CG1a) ✓** — brand/product names, prices, and `% off` are converted to
Unicode bold (`_to_bold` / `_bold_caption`) so the deal pops on Instagram (IG has no markdown).
Never bold whole paragraphs — only names/prices/discounts.

**Disclosure (CG1b) ✓** — do NOT put any "As an Amazon Associate…" sentence in the caption
(the account owner's instruction). The ONLY disclosure is a single `#ad` hashtag (auto-inserted
if missing); the full FTC line lives on the storefront page. `_bold_caption` runs after a
safety strip that removes the disclosure sentence if the model still adds it.

**Grounding (CG1c) ✓** — use ONLY the exact numbers in the candidate rows; NEVER invent
prices/ratings/discounts/claims (Global G13). A tasteful EMOJI PACK throughout (catchy, not
spammy) + 15-25 category-relevant hashtags.

## CG2 — Product description generator ⏳
For each high-priority product emit: (1) short title (2) one-line hook (3) 2–3 sentence
description (4) key benefit (5) ideal customer (6) current price (7) category (8) subcategory
(9) Instagram angle (10) suggested reel hook (11) suggested carousel title (12) suggested
bundle (13) CTA. Every field derives ONLY from available data — never hallucinate specs.

## CG3 — Content formats ⏳
- **Reel:** hook → 3–7 products (short descriptions) → CTA
- **Carousel:** slide 1 hook → slides 2–6 products → final slide CTA
- **Story:** product → price → benefit → CTA
- **Website collection:** SEO title → description → products → related collections
The carousel format is the one wired to posting (see [[carousel-publisher]]).

## CG4 — CTA generator (no false urgency) ✓ tone ⏳ rotation
Rotate varied CTAs: "Check the current price →", "See the full list →", "Find it on
Amazon →", "View today's price →", "Save this list for later.", "Full collection in bio."
NEVER invent urgency ("only 2 left", "ends tonight") or scarcity that the data doesn't show.

## CG5 — Claim safety (HARD RULE) ✓ enforced in prompt
The composer cites only real numbers from the candidate rows (price, rating, reviews,
discount, "bought past month"). It must NOT assert "lowest price ever", "70% OFF", "#1
bestseller", medical/health/weight-loss/treatment benefits, or any spec not present. Fitness
& beauty copy stays to accessories/lifestyle framing — no medical claims. Trend words
("trending", "viral") only when supported by real signal (see [[trend-scout]]).

## CG6 — Compliance ✓ enforced
Disclosure is a single **`#ad`** hashtag in every posted caption (auto-inserted if missing) —
the clean, FTC-friendly form the account owner chose; the verbose "As an Amazon Associate…"
sentence is NOT used in captions (it lives on the storefront page instead). See CG1b + Global
G3. The link that earns is the affiliate link only (built from the real tag).

## CG7 — Hashtags MUST be posted with the caption (HARD RULE) ✓ enforced
The carousel is published with `caption + "\n\n" + hashtags` — the `#ad` + 15-25 tags are
appended to the caption string sent to Instagram (frontend `publishOne`). The caption and
hashtags are ONE published block; never post the caption without its hashtags.

## CG7 — Angle multiplication
For a product with a high Content Potential Score ([[product-scorer]] SC5), propose several
distinct angles/collection homes rather than one caption — this is what turns "a link" into
a content pipeline. Angles feed [[collection-builder]].
