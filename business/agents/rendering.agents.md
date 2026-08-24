# Agent 09 — Rendering (Deterministic Visual System)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Turn an approved `carousel_plan` into pixel-perfect Instagram slide
images using a template-driven design system and **real** property assets.

**Stage & boundary** — Rendering stage. Fully deterministic. Never invents facts or
copy; renders exactly what the plan specifies.

**Inputs** — `carousel_plan` (08) + real assets (03) + brand kit (logo, colors, fonts).

**Outputs** — Slide images at IG specs (1080×1350 portrait / 1080×1080 square),
plus a render manifest `{slide→asset refs, template, overflow_ok}`.

**Tools/models allowed** (recommended in ARCHITECTURE) — **HTML/CSS templates →
Playwright screenshot** (Chromium already ships in the backend image) as the primary
engine; **Pillow/Sharp** for crops/overlays; **SVG** for vector badges/icons. No LLM.

**MUST**
- Render only real source images for property visuals; preserve floor-plan/map
  fidelity (Spec §15, §17). Crop, don't distort; respect aspect ratios.
- Enforce exact IG dimensions and safe margins; keep text within safe areas.
- Apply brand consistently (logo, palette, type). Deterministic + hash-stable.

**Image–text alignment (HARD CONSTRAINTS)** — the overlaid text must sit cleanly on
the image it belongs to:
- **Correspondence.** The text on a slide MUST describe the image beneath it — the
  headline/facts and the bound image come from the SAME slot (Agent 08b). Never render
  a headline about one subject over a picture of another (e.g. a "connectivity"
  headline over a floor plan).
- **Consistent text zone.** Body copy (headline, sub, facts, CTA) occupies a fixed,
  predictable region of the slide (a bottom band by default); it is never scattered
  across the image's focal subject.
- **Legibility scrim.** When text sits over a photo, render a gradient/scrim behind it
  so contrast meets **≥ 4.5:1** (WCAG AA). Text is never placed directly on a busy,
  low-contrast area of the image.
- **Protect the subject.** The text band must not cover the meaningful content of the
  image — the building on a hero, the labels/rooms on a floor plan, the pins/roads on a
  map. Anchor the image so its subject stays in the text-free area; shift the crop
  before shrinking the text.
- **Fit, don't overflow.** Auto-scale/clamp copy so it fits the text zone at a legible
  minimum size; if it still overflows, escalate to QA rather than shrinking illegibly.

**MUST NOT**
- Generate or composite a fake building/interior/amenity (Spec §15).
- Add a fact/number/badge not present in the approved plan.
- Ship a slide with overflowing/cut-off text (hand to QA; regenerate slot).
- Place text over the image's focal subject, or over a photo with no legibility scrim.
- Render copy that does not correspond to the image on the same slide.

**Escalation** — Text overflow or missing asset that can't be cropped cleanly →
flag the slide for QA (10) / Human Review (13); never publish a broken slide.

**Cost budget** — Local render compute only; zero tokens.

**Monitored metrics** — render time/slide, overflow incidents, asset-usage rate,
dimension-compliance rate.

**Failure modes** — long headlines, low-res hero image, missing logo, RTL text →
caught deterministically and surfaced, never silently shipped.
