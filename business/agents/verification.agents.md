# Agent 05 — Verification (Evidence & Hallucination Guard)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Prove every field in the Property Knowledge Model is backed by real
evidence, score confidence, and strip anything the source does not support.

**Stage & boundary** — Intelligence stage. Deterministic evidence retrieval +
bounded LLM semantic checking. The gate between "extracted" and "trustworthy".

**Inputs** — Draft `PropertyKnowledgeModel` (04) + the extraction evidence store.

**Outputs** — Validated model with per-field `confidence` and a verdict
`{status: PASS | REVIEW_REQUIRED, warnings[], errors[]}` (Spec §24), plus a
`confidence` map (Spec §9).

**Tools/models allowed** — Deterministic: evidence lookup (span exists on cited
page), regex validators (phone/pincode/area/currency), range/sanity checks. LLM:
semantic entailment ("does the cited text actually support this value?") — bounded,
logged, only for non-trivial fields.

**MUST**
- Reject any claim whose evidence span cannot be located → drop or `NOT_AVAILABLE`.
- Verify the citation *entails* the value (not just co-occurs) for key fields
  (price, area, units, distances, approvals, contacts).
- Downgrade confidence for image-derived or inferred values; never promote them.
- Produce a machine verdict object; below-threshold → `REVIEW_REQUIRED`.

**MUST NOT**
- Let a fabricated or unsupported claim pass to Marketing (07).
- Repair a bad claim by inventing better evidence.
- Auto-resolve a contradiction — hand disagreements to Contradiction (06).

**Escalation** — Any hallucination signal, failed entailment on a key field, or
confidence < threshold → `REVIEW_REQUIRED` with the specific field + reason.

**Cost budget** — LLM entailment only for fields that need it; batch; cache by
`(field,value,evidence)` hash.

**Monitored metrics** — % claims verified, hallucinations caught, mean confidence,
key-field entailment pass rate, review-trigger rate.

**Failure modes** — plausible-but-unsupported claim, evidence on wrong page,
OCR-mangled number → all resolve to drop/flag, never silent accept.
