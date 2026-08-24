# Agent 01 — Ingestion

> Inherits [../AGENTS.md](../AGENTS.md).

**Mission** — Accept any raw input, identify it reliably, de-duplicate, and record
provenance before a single byte is interpreted.

**Stage & boundary** — Extraction stage, entry point. Deterministic only.

**Inputs** — Uploaded file(s): PDF, scanned PDF, image, DOCX, XLSX, PPTX, CSV, TXT,
screenshots, WhatsApp-shared media, maps.

**Outputs** — `source_document` record: `{sha256, mime, real_type, size, page_count,
origin, received_at, storage_ref, is_duplicate, prior_version_of?}`.

**Tools/models allowed** — content-sniffing MIME detection (magic bytes, not
extension), hashing, object storage. **No LLM.**

**MUST**
- Detect type by **content**, not filename/extension (a `.pdf` may be an image scan).
- Compute `sha256`; an identical hash is a duplicate → link, do not re-store/re-parse.
- Detect a new *version* of a known document (same project, changed bytes) and link
  it as `prior_version_of` for the Versioning flow (Spec §23).
- Persist original bytes immutably with an audit entry (§3).

**MUST NOT**
- Trust the client-supplied MIME/extension.
- Extract or interpret content (that is Extraction's job).
- Store PII outside the controlled store or log raw document bytes.

**Escalation** — Unknown/unsupported/corrupt type → `REVIEW_REQUIRED` with reason.
Encrypted/password-protected file → stop, request credential from owner (never guess).

**Cost budget** — Zero LLM. CPU/IO only.

**Monitored metrics** — ingest count by type, dedup hit rate, version-detection rate,
corrupt/unsupported rate.

**Failure modes** — spoofed type, zero-byte/truncated upload, hash collision guard,
oversized file → all produce explicit typed errors.
