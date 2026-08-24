# Instagram_Business — Real-Estate Marketing Intelligence Platform

The **upstream intelligence layer** that turns raw real-estate documents into
verified property knowledge, audience-specific marketing strategy, and Instagram
carousels — then hands finished assets to the **existing** Instagram engine
(accounts, GitHub-raw hosting, Graph-API publish) via a clean contract. The
existing posting machine is *consumed, not rebuilt* (Spec §26, §33).

> **Status: Phase 1–2 delivered (research + architecture + governance). Phase 3
> (prototype) not started — awaiting go-ahead.** No large pipeline code has been
> written yet, per the project's own "First Task" instruction (Spec §34).

## What's here

| Path | What it is |
|------|-----------|
| [`architecture.html`](architecture.html) | The full **A–S architecture & research analysis** (also published as an Artifact). Open in a browser. |
| [`AGENTS.md`](AGENTS.md) | The **agent constitution** — global rules every agent inherits (evidence-first, LLM policy, security, observability, HITL). |
| [`agents/*.agents.md`](agents/) | 15 **agent charters**, each with Mission · MUST · MUST NOT · Escalation · Cost budget · Monitored metrics. |
| [`schema/property_knowledge.schema.json`](schema/property_knowledge.schema.json) | The normalized **Property Knowledge Model** (JSON Schema, Spec §9). |
| [`benchmarks/dreamz_expected.json`](benchmarks/dreamz_expected.json) | The **benchmark oracle** — expected extraction from `DREAMZ (1).pdf` (a test target, not app config). |

## The four isolated stages (mandatory separation, Spec §33)

```
EXTRACTION            INTELLIGENCE          RENDERING          PUBLISHING
(local OSS + OCR)  →  (API LLM reasoning) → (deterministic) →  (existing IG engine)
facts + evidence      validated knowledge   real-image slides   contract in §K
```

## The 15 governed agents

`00` Orchestrator · `01` Ingestion · `02` Extraction · `03` Multimodal-Vision ·
`04` Property-Entity · `05` Verification · `06` Contradiction (clashes) ·
`07` Marketing-Strategist · `08` Carousel-Planner · `09` Rendering ·
`10` Quality-Control · `11` Security-Privacy · `12` Cost-Governor (subprocess) ·
`13` Human-Review · `14` Integration.

## Non-negotiable rules (see AGENTS.md)

- **Never invent a fact.** Missing → `NOT_AVAILABLE`. Every fact carries evidence.
- **Conflicts are never silently resolved** → `HUMAN_VERIFICATION_REQUIRED`.
- **API LLM (gpt-5-nano) for reasoning/copy only**, behind an `LLMProvider` interface.
  **Local/OSS only for extraction.** Never an LLM for deterministic work.
- **Real images only** — no fabricated buildings/interiors/amenities.
- Every agent is **observable** (trace + cost) and ends in `AUTO_APPROVED /
  REVIEW_REQUIRED / REJECTED`.

## Recommended tech (permissive-license, commercial-safe)

Extraction: **Docling (MIT)** + **pdfplumber (MIT)** + **pypdfium2** + **PaddleOCR
/ Tesseract (Apache)** + **OCRmyPDF (MPL)**. Vision: **open_clip / OpenCV / Pillow**.
Rendering: **HTML/CSS → Playwright** (Chromium already in the backend image).
Store: **PostgreSQL 18 + JSONB (+ pgvector later)** — reuse the running DB.

⚠️ **Excluded for commercial ship:** PyMuPDF (AGPL) and Marker/Surya (GPL + revenue
terms) — see the license analysis in `architecture.html` §C.

## Next step

Phase 3 prototype: `business/` extraction module → knowledge model → validation →
gpt-5-nano marketing + carousel → HTML/Playwright render → `/api/content/generate`
contract, graded automatically against `benchmarks/dreamz_expected.json`.
