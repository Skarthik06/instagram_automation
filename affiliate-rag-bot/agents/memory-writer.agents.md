# Memory Writer Agent

> The "write" half of the flywheel and the closing agent of the run. Persists every
> **successfully-posted** pin to pgvector (for future RAG retrieval) and records its
> ASIN in the PostgreSQL dedup ledger (so it's never pinned again).

**Node:** `store_results` · **Sources:** `graph/nodes.py`, `rag/store.py`, `rag/dedup.py` · **Stage:** 8 of 8

---

## Mission

Turn this run's successes into durable memory so the next run is smarter (better
few-shot context) and cleaner (no repeats). This is what makes the bot compound.

## Inputs

- `state["generated_content"]` — the pins (with content + affiliate links).
- `state["posted_pins"]` — per-pin results from the Publisher.
- pgvector store + `seen_products` ledger — both in the project PostgreSQL DB.

## Outputs

- Side effects only: vectors written to pgvector, ASINs written to `seen_products`.
- `stream_log`, and `errors` on failure. (No new state fields.)

## Tools & Capabilities

- `rag_store.store_pin(...)` — embeds a rich summary (category, product, title,
  description, tags) and persists it with metadata + a unique id.
- `dedup_store.mark_as_pinned(products)` — inserts/increments `seen_products` rows.
- Both writes run **concurrently** via `asyncio.gather` + executor threads.

## Rules & Constraints

- **R1 — Store ONLY successes.** Compute `posted_asins = {r.asin for r in posted_pins
  if r.success}` and persist only the intersecting pins. Never store a pin that failed
  to publish — that would poison RAG and wrongly block re-attempts. (Global G5)
- **R2 — Nothing successful is a clean no-op.** Empty successful set → log + a
  `stream_log` note, no error. (A run that posted nothing legitimately stores
  nothing.)
- **R3 — Single-DB writes.** Both writes go to the project PostgreSQL DB (pgvector
  collection + `seen_products`); embeddings are computed locally. (Global G6, G8)
- **R4 — Idempotent dedup.** `mark_as_pinned` increments `pin_count` if an ASIN
  somehow already exists, rather than erroring — safe even if dedup was bypassed
  upstream (e.g. Dedup Guard's fail-open path).
- **R5 — Off the event loop.** All blocking store/DB work goes through
  `run_in_executor`.
- **R6 — Never raise.** Exceptions → `{"errors": [...]}`; a storage failure must not
  crash the run after pins are already live. (Global G1)
- **R7 — Rich embeddings.** Store a composed summary (not just the title) so future
  similarity search matches on *style/content*, powering the RAG Retriever's
  few-shot examples.

## Relationship to read-side agents

- Pairs with the **RAG Retriever** (stage 4): this agent writes the vectors that
  agent later reads.
- Pairs with the **Dedup Guard** (stage 2): this agent writes the ASINs that agent
  later filters on. Same `dedup_store` / `rag_store` singletons.

## Failure Handling

- Vector or dedup write error → recorded in `errors`; the run still completes (pins
  are already published). Partial writes are tolerated and self-heal next run.

## Done / Success Criteria

Each successfully-posted pin has (a) one document in the pgvector collection and
(b) one row in `seen_products`. A `stream_log` line reports counts and the running
total pinned.

## Notes

This agent is the reason the README calls the system a "flywheel": every run's output
becomes next run's input context, so quality and dedup coverage grow monotonically.
