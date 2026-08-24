# Agent 10 — Quality Control (Pre-Publish Gate)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — The last gate before the existing Instagram engine: verify the
rendered carousel + caption are factually and visually correct (Spec §24).

**Stage & boundary** — Rendering stage exit. Deterministic checks + bounded LLM for
factual cross-check of on-slide/caption claims against the validated model.

**Inputs** — Rendered slides + manifest (09) + caption/hashtags (08) + validated
model (05/06).

**Outputs** — Verdict `{status: PASS | REVIEW_REQUIRED | REJECTED, confidence,
warnings[], errors[]}` (Spec §24).

**Checks — Factual** (every on-slide/caption claim must trace to a verified fact):
project name, location, price, area, BHK, contacts, builder, amenities, approvals,
distances, floor-plan labels, CTA. A claim with no verified backing → error.

**Checks — Visual** (deterministic): text overflow / cut-off, readability/contrast,
image quality, carousel dimensions, duplicate slides, missing logo, missing CTA,
wrong/altered contact number.

**Tools/models allowed** — Deterministic layout/contrast/dimension/dup checks; LLM
only to confirm caption claims are supported (no new facts). No rendering.

**MUST**
- Fail closed: any unverifiable factual claim or contact mismatch → `REJECTED` or
  `REVIEW_REQUIRED`, never PASS.
- Emit specific, actionable errors (e.g. "Price shown but no verified price in
  source" — Spec §24).
- Confirm IG dimensions/slide count are publish-legal.

**MUST NOT**
- Approve fabricated urgency, price, approval, amenity, or altered contact info.
- Modify content to force a pass — it reports, it does not edit.

**Escalation** — Any error → `REVIEW_REQUIRED`/`REJECTED` to Human Review (13); only
a clean pass above threshold may be `AUTO_APPROVED`.

**Cost budget** — Mostly deterministic; LLM claim-check batched + cached.

**Monitored metrics** — pass/review/reject split, top error types, factual-defect
escape rate (post-publish), false-reject rate.

**Failure modes** — subtle contact typo, off-by-one distance, contrast on busy
photo, near-duplicate slides → all explicitly checked.
