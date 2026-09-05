# Trend Scout Agent

> Fetches real-time trending keywords for the category via Tavily, so pin copy weaves
> in language people are actually searching for right now. Fully optional — the
> pipeline runs fine without it.

**Node:** `search_trends` · **Sources:** `graph/nodes.py`, `tools/search.py` · **Stage:** 3 of 8

---

## Mission

Return a deduplicated list of ~15 trending keyword phrases for `state["category"]`
that the Pin Composer can weave into descriptions.

## Inputs

- `state["category"]`, `cfg.amazon.marketplace`.
- `cfg.tavily_api_key` — **optional**.

## Outputs

- `trend_keywords: list[str]`.
- `stream_log`, and `errors` on soft failure.

## Tools & Capabilities

- `fetch_trending_keywords(category, marketplace)` — Tavily search
  (`search_depth=basic`, `max_results=5`, `include_answer=True`), then keyword
  extraction from the AI answer + result snippets, plus a few Pinterest-standard
  terms.
- `_fallback_keywords(category)` — hand-curated defaults per category.

## Rules & Constraints

- **R1 — Optional by design.** No `TAVILY_API_KEY`? Do not error — fall back to
  static keywords and continue. `config.validate()` intentionally does not require
  it. (Global G7 tolerance)
- **R2 — Fail-OPEN.** Any Tavily error (network, quota, auth) → return
  `_fallback_keywords(category)` and continue. Trends are enrichment, never a gate.
  (Global G2 fail-open, G1)
- **R3 — Bounded output.** Cap at 15 keywords; strip stop-words; keep phrases short
  (1–2 words). Downstream the Composer uses at most `MAX_TRENDS = 6`.
- **R4 — No secrets in logs.** Log the query text, never the API key. (Global G8)

## Failure Handling

- Missing key → fallback keywords, no error raised.
- API failure → warning + fallback keywords.
- The node-level `except` returns `{"trend_keywords": [], "errors": [...]}` only if
  extraction itself throws; normal Tavily failures already degrade to fallback inside
  the tool.

## Done / Success Criteria

`trend_keywords` is a non-empty list (from Tavily when available, otherwise the
static fallback). Emptiness downstream is tolerated by the Composer.

## Notes

This is the clearest example of the pipeline's graceful-degradation philosophy: a
missing optional integration lowers quality slightly but never blocks a run.
