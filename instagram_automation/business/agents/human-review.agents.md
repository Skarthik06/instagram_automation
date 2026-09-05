# Agent 13 — Human Review (Human-in-the-Loop)

> Inherits [../AGENTS.md](../AGENTS.md). Implements the three-state control (Spec §25).

**Mission** — Route anything uncertain, conflicting, or risky to a human, and apply
their decision back into the pipeline — high automation *with* controlled verification.

**Stage & boundary** — Control plane. Deterministic workflow/state machine. No LLM,
no fact generation.

**Inputs** — Any agent's `REVIEW_REQUIRED`/`REJECTED` with context: the field/asset/
slide, its evidence, and the reason.

**Outputs** — Human decisions applied: edited values, approved/rejected facts,
template/headline/image changes, slide regenerations, and a final
`AUTO_APPROVED | REVIEW_REQUIRED | REJECTED` state — all audit-logged with who/when.

**Review interface capabilities** (Spec §25) — edit extracted values, approve/reject
facts, change carousel template, edit headline, replace images, regenerate a slide,
approve final content.

**Tools/models allowed** — Workflow state + audit log. Re-invokes the specific
upstream agent to regenerate only the affected artifact (Spec §23).

**MUST**
- Present the evidence beside every value a human is asked to judge.
- Record every human edit/approval/rejection with identity + timestamp (§4).
- On resolution, regenerate **only** affected assets, not the whole campaign.
- Treat human input as authoritative over agent output — but still re-run QA (10)
  before publish.

**MUST NOT**
- Auto-approve anything that failed a hard constraint without explicit human action.
- Lose the linkage between a decision and its evidence/audit trail.

**Escalation** — Stalled review beyond SLA → notify owner; never auto-publish a
pending item.

**Cost budget** — Human time; near-zero compute.

**Monitored metrics** — items in review, mean resolution time, edit rate by field,
auto-approve vs manual ratio, post-review defect rate.

**Failure modes** — reviewer overload, ambiguous evidence, conflicting reviewers →
surfaced with clear context; nothing publishes unresolved.
