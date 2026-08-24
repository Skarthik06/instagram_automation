# Agent 06 — Contradiction (Clashes Detector)

> Inherits [../AGENTS.md](../AGENTS.md). This is the owner-requested "clashes" agent.

**Mission** — Detect conflicting information within and across documents/versions for
the same property and force human resolution — never a silent pick (Spec §11).

**Stage & boundary** — Intelligence stage. Deterministic diffing + bounded LLM only
for semantic equivalence ("2 BHK" vs "2BHK"; "Singapura" vs "Singarapura").

**Inputs** — Validated claims (05) for a property across all its `source_documents`
and prior versions.

**Outputs** — `conflicts[]`: `{field, value_a, source_a, value_b, source_b,
kind: exact|semantic|range, action: HUMAN_VERIFICATION_REQUIRED}` and a per-property
`consistency_report`.

**Tools/models allowed** — Deterministic field-level comparison, numeric tolerance
bands, set-diff for amenities/lists. LLM only to judge whether two strings are the
*same* fact or genuinely different — logged, bounded.

**MUST**
- Compare every shared field across sources and versions (Spec §23).
- Emit `CONFLICT DETECTED` with both values, both sources, and the field.
- Set `action = HUMAN_VERIFICATION_REQUIRED` for every real conflict.
- Distinguish a *conflict* (940 vs 950 sqft) from a *version change over time*
  (price updated) — the latter feeds Versioning, the former blocks the pipeline.

**MUST NOT**
- Silently choose, average, or "prefer the newer" value for a factual conflict.
- Treat formatting/synonym differences as conflicts (dedupe those first).
- Let a conflicted field flow into marketing content.

**Escalation** — Any unresolved conflict on a marketing-relevant field →
`REVIEW_REQUIRED` and the field is withheld until a human resolves it.

**Cost budget** — Mostly deterministic; LLM equivalence checks batched + cached.

**Monitored metrics** — conflicts/property, exact vs semantic vs range split,
false-conflict rate, time-to-resolution.

**Failure modes** — unit mismatches (sqft vs sqm), rounding, stale contact numbers,
multi-phase projects → classified precisely, never collapsed.
