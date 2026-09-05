# Agent 14 — Integration (Hand-off to the Existing Instagram Engine)

> Inherits [../AGENTS.md](../AGENTS.md). The clean boundary to the machine that
> already exists — do not rebuild or tightly couple to it (Spec §26).

**Mission** — Deliver a finished, approved campaign to the existing Instagram
automation system as a stable contract, and record publishing history.

**Stage & boundary** — Publishing edge. Deterministic. Produces the contract; the
existing engine performs the actual upload/caption/schedule/publish.

**Inputs** — `AUTO_APPROVED` campaign: rendered slides + manifest (09), caption +
hashtags + CTA (08), campaign metadata, property_id.

**Outputs** — The integration contract (Spec §26):
```json
{ "campaign_id": "", "property_id": "",
  "carousel": { "slides": [], "images": [] },
  "caption": "", "hashtags": [], "cta": "" }
```
plus a `publishing_history` record on hand-off/acknowledgement.

**Tools/models allowed** — Contract serialization + the existing engine's documented
interface (its accounts, hosting, and Graph-API publish path). No LLM.

**MUST**
- Emit exactly the agreed contract shape; validate it deterministically before send.
- Only hand off content in state `AUTO_APPROVED` that passed QA (10).
- Map assets to the existing engine's expected image inputs; record what was sent.
- Stay decoupled: talk to the engine's interface, never its internals.

**MUST NOT**
- Re-implement posting, scheduling, or account/token handling (already exists).
- Send unapproved/`REVIEW_REQUIRED` content, or mutate the engine's own data model.
- Alter facts/copy at the boundary — it transports, it does not create.

**Escalation** — Contract validation failure or engine rejection → stop, log, and
`REVIEW_REQUIRED`; never silently drop or retry-storm.

**Cost budget** — Serialization only; zero tokens.

**Monitored metrics** — hand-offs, contract-validation pass rate, engine
accept/reject, publish confirmations, time from approval → live.

**Failure modes** — schema drift vs the engine, image-host mismatch, partial
carousel → caught by contract validation before hand-off.
