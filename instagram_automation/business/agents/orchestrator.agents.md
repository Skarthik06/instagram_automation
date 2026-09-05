# Agent 00 — Orchestrator (Pipeline Supervisor)

> Inherits [../AGENTS.md](../AGENTS.md). The "building" agent: it coordinates the
> whole run but performs no domain work itself.

**Mission** — Drive one property through the pipeline stage by stage, enforce
boundaries, collect traces, and decide the final human-in-the-loop state.

**Stage & boundary** — Control plane. Owns *sequencing and policy*, never parsing,
reasoning, or rendering. Delegates each step to the responsible agent.

**Inputs** — A `job` = one or more source documents for one property + campaign
objective (e.g. `site_visit`, `brochure_request`, `awareness`).

**Outputs** — A `campaign` record: property_id, validated knowledge model ref,
marketing intelligence, carousel plan, rendered assets, QA report, final state.

**Tools/models allowed** — Workflow/queue only. **No LLM. No file parsing.**

**MUST**
- Run stages in order (§0) and pass only each stage's typed output forward.
- Short-circuit to `REVIEW_REQUIRED`/`REJECTED` the moment any agent raises it.
- Attach a `run_id` and aggregate every child agent trace + total cost (§4).
- Be idempotent: an unchanged job re-uses cached stage outputs (§6, §28).

**MUST NOT**
- Fabricate or "patch" a downstream input to make a stage pass.
- Call the LLM or touch raw documents directly.
- Continue past a hard-constraint violation or an unresolved `CONFLICT`.

**Escalation** — Any stage error → stop, mark job `error`, preserve partial trace.
Any `CONFLICT` or sub-threshold confidence → `REVIEW_REQUIRED` to Human Review (13).

**Cost budget** — Enforces the per-job LLM budget via Cost Governor (12); aborts if
projected spend exceeds the campaign cap.

**Monitored metrics** — stage latencies, total tokens/cost per job, % jobs
auto-approved vs review, failure rate by stage.

**Failure modes** — partial extraction, stage timeout, budget exceeded, deadlock on
review. Each maps to an explicit terminal state; none may hang silently.
