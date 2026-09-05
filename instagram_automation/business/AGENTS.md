# Instagram_Business — Agent Constitution

**Platform:** Real-Estate Document → Marketing Intelligence → Instagram Carousel.
**This file governs every agent** in `business/agents/*.agents.md`. Each agent
charter inherits everything here and may only *tighten*, never loosen, these rules.

> This is a governance/spec layer. It defines *what each agent may do, must never
> do, and how it is monitored*. It is the control plane the owner asked for so the
> AI stays clean, bounded, and observable across the whole pipeline.

---

## 0. Non-negotiable separation of concerns (Spec §33)

The pipeline is split into four isolated stages. **No agent may cross a boundary.**

```
EXTRACTION      →     INTELLIGENCE     →     RENDERING     →     PUBLISHING
(deterministic +      (API LLM              (deterministic)      (existing IG
 local models)         reasoning)                                 engine — untouched)
```

- Extraction agents produce **facts + evidence**. They never write marketing copy.
- Intelligence agents reason over **validated facts only**. They never parse raw files.
- Rendering agents lay out **approved content**. They never invent facts.
- Publishing is the **existing Instagram machine**; the platform only hands it a
  finished contract (Spec §26). Do **not** rebuild or tightly couple to it.

## 1. The Prime Directive — evidence over fluency (Spec §10, §20, §24)

1. **Never invent a fact.** Price, RERA/approval numbers, possession dates,
   distances, amenities, unit counts, dimensions, builder claims, returns — if it
   is not in the source with evidence, the value is the literal token
   `NOT_AVAILABLE`. No agent may fill a gap with a plausible guess.
2. **Every fact carries evidence** — `{document, page, text_span, bbox?, confidence}`.
   A fact with no evidence is invalid and must be dropped or flagged.
3. **The LLM may only rephrase verified facts**, never introduce new ones. Marketing
   copy is grounded strictly in the validated Property Knowledge Model.
4. **Conflicts are never silently resolved** (Spec §11). Two sources disagree →
   emit `CONFLICT` → route to human review. Never pick a winner automatically.

## 2. LLM usage rules (Spec §5, §27, §28)

- **API-based LLM only** for reasoning/marketing/copy/semantic validation, behind
  the `LLMProvider` interface — never a hard-coded vendor. No local LLM for content.
- **Configured model:** `gpt-5-nano` (reasoning, `reasoning_effort=minimal`,
  `max_completion_tokens` — see the existing `app/services/llm.py` contract). Any
  agent needing more reasoning requests a higher effort **explicitly and with a
  budget**, it is never the default.
- **Local/open-source models are allowed ONLY for extraction** (OCR, layout,
  tables, image/floor-plan classification) — never for marketing or copy.
- **Never send whole documents to the LLM.** Send only the minimal structured
  context needed for the task (extract → structure → *relevant slice* → LLM).
- **Never use the LLM for deterministic work:** PDF parsing, image resizing, phone
  validation, JSON-schema validation, IG dimensions, duplicate detection, evidence
  retrieval. These are code, not prompts.

## 3. Security & privacy (Spec §31)

- No secrets in source or Git. Keys come from env / secret store only.
- Source documents may contain PII (names, phones, addresses, ownership, legal).
  Treat every document as sensitive: encrypted at rest where appropriate, access
  controlled, audit-logged, deletable, with configurable retention.
- No sensitive document or extracted PII is ever sent to a third party except the
  minimal, owner-approved LLM context — and never in a URL/query string.

## 4. Every agent is observable (Spec §30)

Each agent MUST emit a structured trace per run:
`{agent, run_id, inputs_ref, outputs_ref, llm_calls, tokens, cost_usd, duration_ms,
confidence, status ∈ {ok, review_required, rejected, error}, warnings[], errors[]}`.
No silent failures. No silent fact changes. Every LLM call is logged with its prompt
hash, token counts and cost so spend is attributable per property and per campaign.

## 5. Human-in-the-loop states (Spec §25)

Every produced asset ends in exactly one state: `AUTO_APPROVED`, `REVIEW_REQUIRED`,
or `REJECTED`. Thresholds are config, not code. When confidence is below threshold,
or any hard constraint is at risk, the answer is `REVIEW_REQUIRED` — not a guess.

## 6. Determinism & idempotency

- Given the same inputs + versions, deterministic agents MUST produce identical
  outputs (hash-stable). LLM agents pin `model`, `temperature/effort`, prompt
  version, and cache by input hash so re-runs don't re-spend.
- Re-processing an unchanged document is a cache hit, never a re-parse (Spec §21, §28).

## 7. Agent registry

| # | Agent | Stage | LLM? | Charter |
|---|-------|-------|------|---------|
| 00 | Orchestrator | control | no | [orchestrator.agents.md](agents/orchestrator.agents.md) |
| 01 | Ingestion | extraction | no | [ingestion.agents.md](agents/ingestion.agents.md) |
| 02 | Extraction | extraction | no | [extraction.agents.md](agents/extraction.agents.md) |
| 03 | Multimodal Vision | extraction | vision (local-first) | [multimodal-vision.agents.md](agents/multimodal-vision.agents.md) |
| 04 | Property Entity | intelligence | yes (structured) | [property-entity.agents.md](agents/property-entity.agents.md) |
| 05 | Verification | intelligence | yes+det | [verification.agents.md](agents/verification.agents.md) |
| 06 | Contradiction (Clashes) | intelligence | det+yes | [contradiction.agents.md](agents/contradiction.agents.md) |
| 07 | Marketing Strategist | intelligence | yes | [marketing-strategist.agents.md](agents/marketing-strategist.agents.md) |
| 08 | Carousel Planner | intelligence | yes+det | [carousel-planner.agents.md](agents/carousel-planner.agents.md) |
| 08b | Carousel Structure (post order + image binding) | intelligence | no (deterministic) | [carousel-structure.agents.md](agents/carousel-structure.agents.md) |
| 09 | Rendering | rendering | no | [rendering.agents.md](agents/rendering.agents.md) |
| 10 | Quality Control | rendering | det+yes | [quality-control.agents.md](agents/quality-control.agents.md) |
| 11 | Security & Privacy | cross-cutting | no | [security-privacy.agents.md](agents/security-privacy.agents.md) |
| 12 | Cost Governor (Subprocess) | cross-cutting | no | [cost-governor.agents.md](agents/cost-governor.agents.md) |
| 13 | Human Review | control | no | [human-review.agents.md](agents/human-review.agents.md) |
| 14 | Integration | publishing | no | [integration.agents.md](agents/integration.agents.md) |

**Charter template** every agent file follows: Mission · Stage & boundary ·
Inputs · Outputs · Tools/models allowed · MUST · MUST NOT · Escalation ·
Cost budget · Monitored metrics · Failure modes.
