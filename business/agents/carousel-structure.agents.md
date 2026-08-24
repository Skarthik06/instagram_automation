# Agent 08b — Carousel Structure (Post Order & Image Binding)

> Inherits [../AGENTS.md](../AGENTS.md). Extends [carousel-planner.agents.md](carousel-planner.agents.md).
> Implemented by `app/business/carousel_structure.py`.

**Mission** — Enforce a FIXED, evidence-grounded posting structure for every Instagram
carousel: a defined slide order, and a deterministic rule for which image lands on
which slide — so the copy and the image on each slide always match.

**Stage & boundary** — Intelligence stage, deterministic. Emits an ordered slot plan +
per-slot image binding. It does NOT write copy (the LLM does, per slot) and does NOT
render (Agent 09 does).

---

## 0. Constraints at a glance (ENFORCED)

1. **Post structure is fixed** — every carousel follows one of the three ordered
   10-slide structures in §1; slots keep their order (hero first, CTA last).
2. **≥ 10 slides, always**, expanding so **every real PDF image** appears (§2).
3. **Each slot binds ONE image by type** (§2–§3); property slots use only real PDF
   images, context slots only fetched photos / the map.
4. **The image and the text on a slide come from the SAME slot** — so the overlaid
   copy always describes the image under it, and the text is laid out to align with
   (not obscure) that image. The pixel-level alignment/legibility rules are the
   rendering charter's **"Image–text alignment (HARD CONSTRAINTS)"**
   ([rendering.agents.md](rendering.agents.md)); this agent guarantees the pairing that
   makes them possible.

---

## 1. The three approved structures (owner-selected)

Every campaign uses ONE of these. `carousel_type` / angle selects it; batch
recommendations use all three (Investor/Value leads).

**A · Investor / Value** — `investor_value`
1 Hero · 2 Project overview · 3 Price & value · 4 Floor plan · 5 Amenities ·
6 Location (map) · 7 Connectivity · 8 Builder & approvals · 9 Why invest · 10 CTA

**B · Property Tour** — `property_tour`
1 Hero · 2 Overview · 3 Living spaces · 4 Bedrooms · 5 Kitchen & bath ·
6 Amenities · 7 Floor plan · 8 Location (map) · 9 Connectivity · 10 CTA

**C · Location-First** — `location_first`
1 Hero · 2 Overview · 3 Amenities · 4 Floor plan · 5 Location (map) ·
6 Connectivity · 7 Schools & hospitals · 8 Shopping & lifestyle · 9 Builder trust · 10 CTA

Each slot declares a `role` (property | context | cta) and a ranked list of the real
image `asset_types` it accepts.

## 2. Compulsory rules (MUST)

- **Minimum 10 slides.** Always. `slide_count < 10` is raised to 10.
- **Use EVERY real PDF image — none missed.** Real brochure images (all
  `PROPERTY_TYPES`, logos/scans excluded) are counted; the carousel auto-expands with
  extra gallery slides so each image gets its own slot, up to Instagram's 20-slide cap.
  The small-size `usable` flag is deliberately ignored for real images (slides render
  at 2160px; a small crop scales up).
- **PDF-images-first, matched by slot.** Property/CTA slots are filled from the real
  images, preferring the slot's asset type (hero→exterior, floor_plan→floor plan,
  bedrooms→bedroom …). If the brochure lacks that type, the next unused real image is
  used; when all are placed, real images are reused (round-robin).
- **Copy matches the image.** The same slot drives both the LLM copy and the bound
  image, so headline + facts + picture always align.

## 3. MUST NOT

- **Never place a context/fetched photo on a property or CTA slot** (this was the bug:
  hospital on "features", supermarket on "builder", fax on CTA). Context photos and the
  OSM map appear ONLY on `context` slots (location / connectivity / nearby).
- Never drop or skip a real brochure image while filling a slot with a stock photo.
- Never invent a fact to fill a slot (charter §1); an image-scarce slot reuses the
  closest real image, never fabricated visuals.

## 4. Context-slot image matching

`context` slots pull the OSM map (`context_map` / `location_map`) for the location slot,
and a subject-matched fetched photo (metro / school / hospital / mall) for connectivity
and nearby slots — matched by the photo's category to the slot subject.

## 5. Monitored metrics

structure used, slides/plan, distinct real images used vs available (target = all),
context-on-property-slot count (**must be 0**), fact-coverage per slide.

## 6. Failure modes

Too few real images → reuse real images (never context) + design background.
More images than the 20-slide cap → keep the highest-confidence images, flag overflow.
No viable structure → `REVIEW_REQUIRED` (charter escalation), never fabrication.
