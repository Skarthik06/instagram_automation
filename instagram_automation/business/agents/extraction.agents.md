# Agent 02 — Extraction (Deterministic Document Understanding)

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Turn a source document into layout-aware, coordinate-anchored text,
tables, and image regions — with page + bounding-box provenance for every span.

**Stage & boundary** — Extraction stage. Deterministic + local open-source models
only. Produces evidence primitives, never property fields or copy.

**Inputs** — A `source_document` from Ingestion (01).

**Outputs** — `extraction` bundle: reading-ordered text blocks, tables (as
structured cells), image regions (page, bbox, ref), per-span `{page, bbox,
confidence, method}`. Ligatures/glyph artifacts normalized (e.g. `→fi`).

**Tools/models allowed** (commercial-safe, permissive licenses — see ARCHITECTURE):
- Digital PDF: **Docling (MIT)** primary; **pdfplumber (MIT)** deterministic cross-check.
- Page raster / image extraction: **pypdfium2 (permissive)**.
- Scanned/image text: **PaddleOCR (Apache-2.0)**, **Tesseract (Apache-2.0)** fallback,
  **OCRmyPDF (MPL-2.0)** to make scans searchable.
- Tables: Docling table model; camelot/pdfplumber cross-check.
- **AGPL PyMuPDF is disallowed** for the shipped product unless a commercial license
  is purchased (see ARCHITECTURE license analysis).
- **No content LLM.**

**MUST**
- Preserve **reading order** and **bounding boxes**; every text span keeps its origin.
- Choose OCR path only when the page is image-only or text coverage is poor
  (measured, not guessed) — a digital-text page is never sent to OCR.
- Normalize known glyph/ligature corruption and de-hyphenate line breaks.
- Emit a per-span confidence and the extraction `method` used.

**MUST NOT**
- Map anything to the property schema (that is Property Entity, 04).
- Drop the coordinate/provenance data — downstream evidence depends on it.
- "Fix" garbled text by inventing words; low-confidence spans stay flagged.

**Escalation** — OCR confidence below floor, or unreadable region → mark region
`low_confidence` and pass through; never silently discard.

**Cost budget** — Local compute only; zero API tokens (Spec §28 cost lever).

**Monitored metrics** — chars/page, OCR-invoked %, mean span confidence, table
extraction success, glyph-normalization count, ms/page.

**Failure modes** — image-only PDF with no OCR text, rotated pages, multi-column
interleave, non-Latin scripts → each degrades gracefully with flags, never crashes.
