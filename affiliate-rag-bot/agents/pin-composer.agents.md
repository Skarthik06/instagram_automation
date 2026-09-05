# Pin Composer Agent

> The single LLM brain of the pipeline. In **one** structured `gpt-5-nano` call it
> both SELECTS the best products (by commission + Pinterest fit) and WRITES every
> pin (title, description, hashtags) — schema-guaranteed, no text parsing.

**Node:** `compose_pins` · **Sources:** `graph/nodes.py`, `chains/compose.py` · **Stage:** 5 of 8

---

## Mission

Turn `fresh_products` (+ trends + RAG context) into `products_per_run` finished pins.
This node replaces the old two-stage rank→write design (1 + N calls) with exactly one
call that ranks and writes together.

## Inputs

- `state["fresh_products"]`, `state["trend_keywords"]`, `state["rag_context"]`,
  `state["rag_product_ideas"]`, `state["products_per_run"]`.
- `cfg.openai_api_key`, `cfg.openai_model` (default `gpt-5-nano`).

## Outputs

- `ranked_products: list[ProductData]` — the chosen products, best first.
- `generated_content: list[PinContent]` — each with `pin_title`, `pin_description`
  (FTC-terminated), `hashtags` (≤5), and an empty `affiliate_link` (filled at
  stage 6).
- `stream_log`, and `errors` on failure/empty.

## Tools & Capabilities

- `chains.compose.compose_pins(...)` — builds the prompt and calls
  `ChatOpenAI(...).with_structured_output(PinBatch)`.
- Output schema (Pydantic, function-calling enforced):
  - `PinDraft{ id, pin_title, pin_description, hashtags[] }`
  - `PinBatch{ pins: PinDraft[] }`

## Rules & Constraints (the strictest in the system)

- **R1 — Exactly ONE LLM call per run.** No per-product calls, no retry loops. Trends
  and RAG context are sent once. (Global G10)
- **R2 — Structured output only.** Force the schema via `with_structured_output`; do
  not parse free-text JSON. Malformed model output is prevented, not repaired.
- **R3 — Token discipline.** Compact pipe-delimited candidate rows
  (`id|title|price|category`), titles truncated to `TITLE_CHARS = 70`, at most
  `MAX_CANDIDATES = 15` candidates, `MAX_TRENDS = 6`, `MAX_EXAMPLES = 2`,
  `MAX_IDEAS = 5`, static (cache-friendly) system prompt, `max_tokens = 900`.
- **R4 — Ranking policy is fixed.** Prefer commission rate (Fashion 9% > Home 8% >
  Kitchen 7% > Beauty 6% > Electronics 2–5%), Pinterest visual appeal, the ₹500–5000
  impulse range, and similarity to proven winners.
- **R5 — FTC disclosure is mandatory.** Every description must end with
  `#Ad | As an Amazon Associate I earn from qualifying purchases.` The prompt requires
  it AND a code-level safety net re-appends it if the model omits it. Never ship a pin
  without it. (Global G3)
- **R6 — Validate model indices.** Only accept `PinDraft.id` within
  `range(len(products))`; silently drop out-of-range picks (no hallucinated
  products).
- **R7 — Shape guarantees.** ≤5 hashtags, `#` stripped; titles/descriptions trimmed;
  return at most `count` pins.
- **R8 — Cold-start capable.** With empty RAG context, the "PROVEN winners" block
  becomes "none yet (cold start — use your expertise)". (Global G7)
- **R9 — Empty output aborts.** No usable pins → empty outputs + error; the
  `_has_content` gate aborts to `END`. Never proceed to posting with nothing.
  (Global G2 fail-closed)
- **R10 — Never raise.** Exceptions → `{"ranked_products": [], "generated_content":
  [], "errors": [...]}`. (Global G1)

## Failure Handling

- API/auth error → captured in `errors`, empty content, clean abort.
- Model returns fewer than `count` valid pins → keep what validated; if zero, abort.

## Done / Success Criteria

`generated_content` is a non-empty list of well-formed `PinContent` dicts, each with a
FTC-terminated description and ≤5 hashtags, ordered best-first.

## Notes

This is the only place cost is incurred per run. Any change that adds LLM calls or
inflates the prompt directly raises cost and latency — guard it carefully.
