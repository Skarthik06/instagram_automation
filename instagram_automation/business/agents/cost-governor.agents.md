# Agent 12 — Cost Governor (Subprocess / Budget Control)

> Inherits [../AGENTS.md](../AGENTS.md). The owner-requested "subprocess" control:
> it meters and gates every expensive sub-operation (Spec §28).

**Mission** — Minimize API spend without hurting quality: enforce budgets, cache
aggressively, deduplicate work, and keep the LLM out of deterministic tasks.

**Stage & boundary** — Cross-cutting. Deterministic. Wraps/authorizes every LLM call
and heavy subprocess; can deny or downgrade a call over budget.

**Inputs** — Proposed LLM/vision calls from any agent (model, effort, est. tokens,
input hash) + per-job / per-campaign budgets.

**Outputs** — Allow/deny/downgrade decisions, cache hits, and a live spend ledger per
property and campaign (§4).

**Tools/models allowed** — Deterministic: response cache (by input+prompt+model
hash), token estimator, budget ledger, rate limiter, retry/backoff policy. No LLM.

**MUST**
- Enforce the funnel: `raw → local/OSS extraction → structured → relevant slice →
  LLM` — reject calls that would send whole documents (Spec §28, §2).
- Return a cache hit instead of re-calling for identical input (§6); reuse extracted
  knowledge across channels (Spec §21) rather than re-parsing.
- Keep the configured cheap model default (gpt-5-nano, minimal effort); require an
  explicit, budgeted justification to raise effort/model.
- Maintain a per-campaign spend ceiling; block and escalate on breach.

**MUST NOT**
- Authorize an LLM call for deterministic work (parsing, resizing, validation,
  dedup, dimensions, evidence retrieval — §2).
- Allow uncached duplicate calls or unbounded retries.

**Escalation** — Budget ceiling hit → deny + `REVIEW_REQUIRED` to owner with the
spend breakdown; repeated cache misses on identical inputs → alert (cache bug).

**Cost budget** — It *is* the budget authority; near-zero overhead.

**Monitored metrics** — tokens & USD per property/campaign, cache-hit rate,
deterministic-vs-LLM ratio, calls blocked/downgraded, retry counts.

**Failure modes** — prompt drift busting the cache, token underestimate, runaway
retry loop → all bounded by ledger + rate limits.
