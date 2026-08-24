# Agent 04 — Property Entity (Structured Knowledge Mapping)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Map extracted evidence primitives into the normalized Property
Knowledge Model (Spec §9), attaching source evidence to every field it fills.

**Stage & boundary** — Intelligence stage, entry. API LLM in **structured-output**
mode over *relevant extracted context only* — never over raw files.

**Inputs** — Extraction (02) spans/tables + Multimodal (03) asset facts, pre-filtered
to the slices relevant to each schema field.

**Outputs** — A draft `PropertyKnowledgeModel` where every populated field is a
`claim = {field, value, confidence, source:{document,page,text|bbox}}`, and every
absent field is the literal `NOT_AVAILABLE`. Supports apartments, villas, plots,
sites, land, commercial, rental, resale, new projects.

**Tools/models allowed** — `LLMProvider.structured_output()` (gpt-5-nano,
minimal effort) + deterministic JSON-schema validation. Deterministic parsers for
phones, pincodes, areas, currency — **not** the LLM (§2).

**MUST**
- Fill a field **only** when backed by an evidence span; else `NOT_AVAILABLE`.
- Emit the exact schema (Spec §9) and pass deterministic schema validation.
- Keep units and raw text as found (e.g. `940 Sqft`, `1.25 acres`) plus a parsed
  numeric — parsing is deterministic and separately evidenced.
- Normalize entities (project/builder/locality) without inventing unseen ones.

**MUST NOT**
- Infer price, RERA, possession, distances, amenities, unit counts, dimensions, or
  returns that are not in evidence (§1, Spec §10).
- Merge two conflicting values — surface both and defer to Contradiction (06).
- Read from original documents directly or paraphrase beyond the source meaning.

**Escalation** — Field with weak/partial evidence → low confidence, flagged for
Verification (05). Structurally ambiguous document → `REVIEW_REQUIRED`.

**Cost budget** — One primary structured call per document set; chunk only if
context exceeds limits; cache by extraction hash (§6).

**Monitored metrics** — fields populated vs `NOT_AVAILABLE`, mean field confidence,
schema-validation pass rate, tokens/property.

**Failure modes** — hallucinated field (caught by Verification), unit ambiguity,
multi-config brochures (multiple BHK/areas) → modelled as a list, never flattened.
