# Agent 08 — Carousel Planner

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Select the best carousel *strategy* for the chosen angle and available
assets, then produce a structured, per-slide plan (copy + which real asset to use).
Not one fixed structure for every property (Spec §13, §14, §20).

**Stage & boundary** — Intelligence stage. Deterministic strategy selection + LLM
slide copy grounded in verified facts. Emits a plan; does **not** render.

**Inputs** — `marketing_intelligence` (07) + validated model + classified assets (03).

**Outputs** — `carousel_plan`: ordered `slides[]`, each
`{slide_number, template, headline, subheadline, facts[](verified), image_ref(real),
badges[], cta, theme, brand}` (Spec §14) + structured `caption` object (Spec §20)
`{hook, body, key_points[], cta, hashtags[], location_tags[], keywords[]}`.

**Strategies** (Spec §13) — Property Discovery, Location First, Family First, Floor
Plan First (extensible). Selected by angle + which assets/facts actually exist.

**Tools/models allowed** — Deterministic strategy rules + slot-filling; LLM for slide
copy only, over verified facts. IG dimension/slot logic is deterministic (§2).

**MUST**
- Pick a strategy whose required slides can be filled by **verified facts + real
  assets**; drop or substitute a slide whose asset/fact is missing.
- Reference only real images (03); mark a slide `needs_asset` rather than inventing.
- Keep every on-slide fact traceable to a verified claim.
- Produce caption/hashtags grounded in the model; no fabricated tags/claims (§20).

**MUST NOT**
- Force a fixed 7-slide template regardless of data.
- Place an unverified fact, fake urgency, or fabricated price/approval on a slide.
- Use a floor-plan/map slide when no real floor-plan/map asset exists.

**Escalation** — No viable strategy meets the minimum verified-slide count →
`REVIEW_REQUIRED`.

**Cost budget** — One copy-generation pass per plan; cache by
`(strategy, model_hash, goal)`.

**Monitored metrics** — strategy distribution, slides/plan, % slides with real
asset, fact-coverage per slide, tokens/plan.

**Failure modes** — missing floor plan/map, too few images, over-long copy → handled
by slot rules and QA (10), never by fabrication.
