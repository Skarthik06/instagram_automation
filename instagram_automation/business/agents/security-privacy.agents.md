# Agent 11 — Security & Privacy (Cross-Cutting Guard)

> Inherits [../AGENTS.md](../AGENTS.md). Runs across every stage (Spec §31).

**Mission** — Protect sensitive real-estate data end to end: PII, ownership/legal
info, secrets — and keep an auditable trail.

**Stage & boundary** — Cross-cutting policy enforcement. Deterministic. May block any
stage that would leak or mishandle sensitive data.

**Inputs** — Every document, extracted field, LLM request payload, storage/logging
operation, and output leaving the platform.

**Outputs** — Allow/deny decisions, PII inventory per document, redaction maps, audit
log entries, retention actions.

**Tools/models allowed** — Deterministic PII detection (regex + validators for phone,
email, address, ID), secret scanners, access-control checks. No LLM required.

**MUST**
- Keep secrets/keys out of source and Git; load from env/secret store only.
- Encrypt sensitive documents/fields at rest where appropriate; enforce access
  control and write an audit entry for every access.
- Minimize LLM payloads to the smallest necessary slice; never send raw full
  documents or unneeded PII to any external API (§2, §3).
- Support document deletion and configurable retention; honor deletion fully.

**MUST NOT**
- Put PII/sensitive data in URLs, query strings, logs, or third-party calls.
- Persist secrets in the DB or commit sensitive documents to version control.
- Allow an output containing unredacted owner/legal PII to reach a public channel.

**Escalation** — Detected secret in a document, attempted PII egress, or
access-control violation → block + `REVIEW_REQUIRED` + audit alert.

**Cost budget** — Deterministic; negligible.

**Monitored metrics** — PII detections/doc, egress blocks, audit completeness,
retention-policy compliance, secret-scan hits.

**Failure modes** — PII embedded in an image, phone number inside a floor plan,
credentials in a shared file → detected and contained, never forwarded.
