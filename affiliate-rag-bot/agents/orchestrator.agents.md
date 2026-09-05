# Orchestrator Agent

> Owns the pipeline graph, the shared browser session, and the run lifecycle. It does
> not do domain work itself — it wires the eight worker agents together, decides when
> to abort, and streams progress to the UI.

**Sources:** `graph/workflow.py`, `graph/state.py`, `pipeline_runner.py`, `server.py` (`RunManager`)
**Stage:** 0 — supervises stages 1–8

---

## Mission

Execute one full pass of the affiliate pipeline: launch a stealth Playwright browser,
build the initial `BotState`, stream the 8-node LangGraph run, mark early aborts, and
emit a clean summary — for both the CLI dashboard and the web dashboard.

## Responsibilities

1. **Build the graph** (`build_graph`): register the 8 nodes, set `scrape_amazon` as
   entry, wire the edges and the three conditional aborts, and compile a singleton.
2. **Own the browser** (`pipeline_runner.run_pipeline`): one Chromium context with
   stealth flags, `en-IN` locale, a desktop UA, `navigator.webdriver` masked, and two
   pages (`amazon_page`, `pinterest_page`) passed to nodes via `config.configurable`.
3. **Seed state**: all list fields initialized empty; `category` and
   `products_per_run` from the caller; `dry_run` flag threaded through.
4. **Stream events**: translate `graph.astream` updates into UI events
   (`run_start`, `node`, `log`, `summary`, `error`) and optimistically mark the next
   node "running".
5. **Enforce one-run-at-a-time** (`server.RunManager`): reject a `start` while a run
   is active; fan events out to every connected browser tab; keep a snapshot so a tab
   joining mid-run catches up.

## Inputs

- `category: str`, `products_per_run: int`, `dry_run: bool` (from CLI args or WS msg).
- Validated `cfg` (calls `cfg.validate()` before launching the browser).

## Outputs (UI event stream)

`{type: run_start|node|log|summary|error, ...}` — the single source of truth consumed
by `main.py` (Rich dashboard) and `server.py` (WebSocket).

---

## Rules & Constraints

- **R1 — Validate before spending resources.** Call `cfg.validate()` first; on
  `ValueError`, emit a `log`(error) + fatal `error` event and return *before*
  launching a browser. (Global G8)
- **R2 — Conditional aborts are the only early exits.** Route to `END` when:
  - `scrape_amazon` yields no `raw_products` (`_has_raw` → abort),
  - `check_duplicates` leaves no `fresh_products` (`_has_fresh` → abort),
  - `compose_pins` yields no `generated_content` (`_has_content` → abort).
  These are correctness gates — do not weaken them. (Global G2)
- **R3 — Never leak the browser.** Always `await browser.close()` in a `finally`,
  even on crash.
- **R4 — Crash containment.** Any unexpected exception during the run becomes a
  `log`(error) + `error` event; the run aborts cleanly, it never propagates raw.
  (Global G1)
- **R5 — Single active run.** `RunManager.start` returns `False` if `status ==
  "running"`; surface "A run is already in progress." Never start a second browser.
  (Global G9)
- **R6 — Node order is canonical.** `NODE_ORDER` in `pipeline_runner.py` must match
  the graph in `graph/workflow.py`. If you add/remove a node, update both plus
  `main.NODE_LABELS` and `server.NODE_META`.
- **R7 — Terminal states are honored.** On finish, any node still `pending`/`running`
  (e.g. after an abort) is marked `skipped`; record `finished_at` and emit a final
  `status` event.
- **R8 — Do not do domain work here.** The orchestrator never scrapes, calls the LLM,
  or posts. It only sequences agents and moves state.

## Failure Handling

- Missing config → fatal, pre-browser, no side effects.
- Node error → captured in `state["errors"]`, surfaced as a `log`(error) event; the
  graph continues unless a conditional gate aborts it.
- Fatal crash → `error` event, browser closed, run ends.

## Done / Success Criteria

A `summary` event is emitted with `category`, `elapsed`, `posted` count, accumulated
`errors`, and the full `log`. `posted` counts only entries in `posted_pins` with
`success == True`.

## Notes

- Both entry points MUST go through `run_pipeline` — it is the sanctioned executor.
- The graph is compiled once as a module-level singleton (`graph`). Treat it as
  immutable at runtime.
