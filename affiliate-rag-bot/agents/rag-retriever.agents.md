# RAG Retriever Agent

> The "read" half of the flywheel. Queries the pgvector pin memory for (A) similar
> past pins to use as few-shot style examples and (B) product types that have
> historically performed well — biasing the Composer toward proven winners.

**Node:** `rag_retrieve` · **Sources:** `graph/nodes.py`, `rag/store.py` · **Stage:** 4 of 8

---

## Mission

Give the Pin Composer memory of what has worked before, so pin quality compounds over
runs. On a cold store this returns nothing — which is fine.

## Inputs

- `state["category"]`, `state["fresh_products"]` (top titles build the query).
- pgvector collection `affiliate_pins` in the project PostgreSQL DB (`cfg.storage.sqlalchemy_url`).
- Local embeddings: `all-MiniLM-L6-v2` (free, CPU, no API key).

## Outputs

- `rag_context: list[RAGContext]` — similar past pins (title, description, category,
  product_title, relevance score).
- `rag_product_ideas: list[str]` — proven product-type titles for this category.
- `stream_log`, and `errors` on failure.

## Tools & Capabilities

- `rag_store.retrieve_similar_pins(query, category, n=5)` — cosine similarity search
  with relevance scores, filtered to `doc_type=pin` (+ category).
- `rag_store.discover_product_ideas(category, n=8)` — distinct proven product titles.
- Both queries run **concurrently** via `asyncio.gather` + executor threads.

## Rules & Constraints

- **R1 — Cold start is normal.** An empty or missing store MUST return `[]` for both
  outputs and continue — never treat emptiness as an error. First runs generate
  purely from product data + trends. (Global G7)
- **R2 — Fail-OPEN.** Any retrieval error → empty context + recorded error; the run
  proceeds. Retrieval is enrichment, not a gate. (Global G2 fail-open, G1)
- **R3 — Read-only.** This agent never writes to pgvector. Writing is the Memory
  Writer's job (stage 8). Keep the read/write split clean.
- **R4 — Local embeddings.** Embeddings run locally (all-MiniLM-L6-v2, CPU, no API
  key); only the resulting vectors and metadata live in your PostgreSQL DB. (G6, G8)
- **R5 — Bounded context.** Retrieve small `n` (5 pins / 8 ideas); the Composer
  further trims to `MAX_EXAMPLES = 2` and `MAX_IDEAS = 5` for token discipline.
  (Global G10)

## Failure Handling

- Missing collection / first run → `[]`, `[]`, no fatal error.
- Embedding model download (~80 MB) happens lazily on first use; subsequent runs are
  fast. A load failure degrades to empty context.

## Done / Success Criteria

`rag_context` and `rag_product_ideas` are populated when history exists, empty on cold
start. Either way the pipeline advances to `compose_pins`.

## Notes

Relevance scores come from normalized embeddings + pgvector's cosine distance
strategy, giving clean 0–1 scores. This agent is what makes the bot "get smarter with
every run."
