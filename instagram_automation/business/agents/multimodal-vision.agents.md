# Agent 03 — Multimodal Vision (Image / Floor-Plan / Map Intelligence)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Understand the *visual* assets in a document: classify every image,
detect floor plans / maps / logos, read dimension callouts, and bind visuals to the
structured facts they evidence (Spec §8, §16, §17).

**Stage & boundary** — Extraction stage (visual). Local-first vision; API vision
(gpt-5-nano accepts image input) allowed **only** for hard extraction cases, never
for marketing reasoning.

**Inputs** — Image regions from Extraction (02) + raster page crops.

**Outputs** — For each asset: `{asset_type, page, bbox, quality, resolution,
aspect_ratio, is_duplicate, blurry, usable, recommended_slide_use, confidence,
source_ref}`. For floor plans: detected room labels + dimensions with evidence. For
maps: flagged as `location_map` with the distinction SOURCE vs CALCULATED preserved.

**Asset taxonomy** (Spec §16) — building_exterior/interior, living_room, bedroom,
kitchen, bathroom, balcony, amenity, kids_area, sports, parking, landscape,
floor_plan, site_plan/cluster_plan, location_map, logo, builder_logo,
document_scan, unknown.

**Tools/models allowed**
- Deterministic image ops (resize, hash, blur/quality, dedup): **OpenCV / Pillow**.
- Zero-shot classification: local **open_clip (permissive)** first.
- Floor-plan / region detection: local detector (e.g. layout/vision model, permissive).
- **API vision (gpt-5-nano) only** as a bounded fallback for ambiguous/critical
  assets, logged and budgeted like any LLM call.

**MUST**
- Prefer and preserve **real source images** — never fabricate or AI-generate a
  building/interior/amenity to represent a real property (Spec §15).
- Bind each visual to its structured fact with evidence + confidence.
- Keep the original floor-plan/map image; never redraw it inaccurately (Spec §17).
- Deterministic dedup + quality/blur gating before any usability verdict.

**MUST NOT**
- Read numbers/dimensions off an image and treat them as verified without evidence
  and a confidence — dimensions from images are flagged for verification.
- Use API vision as the default classifier (cost + §5). Local first.
- Present a decorative/generated asset as a real property visual.

**Escalation** — Ambiguous asset after local + one bounded API pass → `unknown` +
`REVIEW_REQUIRED`. Blurry/low-res but factually important → flag `not_usable`.

**Cost budget** — Local inference free; API-vision fallback capped per document and
attributed via Cost Governor (12).

**Monitored metrics** — assets/doc, classification confidence, floor-plan/map
detection recall, dedup rate, API-vision fallback %, cost/doc.

**Failure modes** — table-rendered-as-image, watermarked stock, collage pages,
rotated maps → flagged, never force-classified.
