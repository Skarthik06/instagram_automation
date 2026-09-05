# Dedup Guard Agent

> Enforces the "never re-pin the same product" rule. Filters scraped products against
> the PostgreSQL `seen_products` ledger of every ASIN ever pinned, so each run only
> works on genuinely new products.

**Node:** `check_duplicates` · **Sources:** `graph/nodes.py`, `rag/dedup.py` · **Stage:** 2 of 8

---

## Mission

Split `raw_products` into `fresh_products` (never pinned) and `duplicate_asins`
(already pinned), using an indexed primary-key lookup on the `seen_products` table.
If nothing fresh remains, the run aborts — there is nothing new to post.

## Inputs

- `state["raw_products"]` — from the Amazon Scraper.
- PostgreSQL `seen_products` table in the project DB (`cfg.storage.sqlalchemy_url`).

## Outputs

- `fresh_products: list[ProductData]` — `raw_products` minus already-pinned ASINs.
- `duplicate_asins: list[str]` — the ASINs filtered out.
- `stream_log`, and `errors` on failure.

## Tools & Capabilities

- `dedup_store.filter_unseen(products)` → `(new, duplicate_asins)`.
- `dedup_store.stats()` → `{total_seen, by_category}` for logging.
- Runs the blocking SQLAlchemy calls in an executor thread (never blocks the event
  loop).

## Rules & Constraints

- **R1 — Correctness before completeness.** A single ASIN match in `seen_products` is
  sufficient to exclude a product. Never re-pin. (Global G5)
- **R2 — Fail-OPEN.** If the dedup lookup itself errors, continue with **all** raw
  products (`fresh_products = raw`, `duplicate_asins = []`) and record the error — a
  broken ledger must not halt earning. (Global G2 fail-open, G1)
- **R3 — All-duplicate is a clean abort.** If every product is already pinned, return
  empty `fresh_products` + an explanatory error; the `_has_fresh` gate aborts to
  `END`. This is expected, not a fault. (Global G2 fail-closed on empty)
- **R4 — Same DB as the vector store.** The `seen_products` table lives in the same
  PostgreSQL database as the pgvector store; `Base.metadata.create_all` auto-creates
  it on first use. One `DATABASE_URL` for both. (Global G6)
- **R5 — Off the event loop.** DB work goes through `run_in_executor`;
  `check_same_thread=False` is intentional so executor threads can share the engine.
- **R6 — Two-layer uniqueness (mandatory).** Every retrieval must apply BOTH:
  1. **Within-scrape dedup** (`tools/amazon._dedup_products`) — collapse variant/duplicate
     listings by exact ASIN, base image id (Amazon image URL before `._`), AND normalized
     title prefix. Amazon lists one product under many ASINs with the same photo; a carousel
     must never show the same product twice.
  2. **Cross-run dedup** (this agent) — filter against `seen_products`.
- **R7 — Embeddings on store (the flywheel).** The content service (`/api/generate`,
  `content_only`) stores EVERY returned product: `store_results` embeds it into pgvector
  (`rag/store`) and marks its ASIN `seen` (`rag/dedup`). Result: each retrieval yields
  products that are unique vs. every prior retrieval — verified (Run A 10 unique → Run B 0
  overlap). Never disable this write; it is what makes posts unique. (Global G6)
- **R8 — Target the requested count; never pad or repeat.** Aim to return the requested
  number (e.g. 10 — Instagram's carousel max). Scrape a deep pool (60 raw → keep 40 unique)
  so a full 10 usually survive dedup + seen-filter. But if the fresh unique pool is smaller,
  return FEWER — never repeat a product and never fabricate one to hit the number. A smaller
  honest post beats a padded one. (Global G15/G16)

## Relationship to the Memory Writer

This agent **reads** the ledger; the Memory Writer (`store_results`, stage 8)
**writes** to it — and only for successfully-posted pins. Together they close the
dedup loop. Both use the same `dedup_store` singleton.

## Failure Handling

- Missing table → auto-created by `_get_session`.
- Query error → fail-open with all products + error recorded.
- Empty input → returns empty lists + error (upstream scrape produced nothing).

## Done / Success Criteria

`fresh_products` contains only products whose ASIN is absent from `seen_products`;
`duplicate_asins` lists the excluded ones; a `stream_log` line reports the split.

## Notes

A relational table (not pgvector) is deliberate: dedup is an exact ASIN lookup
(O(log n) indexed PK), not a similarity search. Keep it that way.
