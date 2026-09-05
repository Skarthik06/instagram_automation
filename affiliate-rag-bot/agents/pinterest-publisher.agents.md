# Pinterest Publisher Agent

> The only agent that performs an outward-facing side effect. Publishes each finished
> pin to Pinterest with human-like typing and long anti-shadowban delays between
> posts. Honors dry-run.

**Node:** `post_pinterest` · **Sources:** `graph/nodes.py`, `tools/pinterest.py` · **Stage:** 7 of 8

---

## Mission

Log into Pinterest, ensure the target board exists, and publish every pin in
`generated_content`, recording a per-pin success/failure result.

## Inputs

- `state["generated_content"]` (now with affiliate links).
- `cfg.pinterest.{email, password, board_name}`, `cfg.bot.delay_between_pins`.
- `pinterest_page`; `dry_run` from `config.configurable`.

## Outputs

- `posted_pins: list[PostResult]` — `{asin, title, success, error}` per pin.
- `stream_log`, and `errors` on failure.

## Tools & Capabilities

- `pinterest_login(page, email, password)` — idempotent (detects avatar), dismisses
  popups.
- `ensure_board_exists(page, board_name)` — creates the board if missing.
- `create_pin(...)` — downloads the product image to a temp file, uploads it, types
  title/description(+hashtags)/affiliate link with human cadence, selects the board,
  clicks Publish, then cleans up the temp image.

## Rules & Constraints

- **R1 — Anti-shadowban pacing is mandatory.** Wait `cfg.bot.delay_between_pins`
  (default 1200s / 20 min) between posts; only the final pin skips the wait. Config
  warns below 600s — never post in a tight loop. (Global G4)
- **R2 — Human-like everything.** All fields use `_human_type` (randomized per-key +
  inter-action delays). Preserve the stealth context set by the Orchestrator. (G4)
- **R3 — Dry-run posts nothing.** When `dry_run` is true, log the intended pin and
  record `success=True` without touching Pinterest. (Global G12)
- **R4 — FTC disclosure survives to publish.** The description sent to Pinterest is
  `pin_description` + hashtags; do not strip the disclosure the Composer added.
  (Global G3)
- **R5 — Per-pin isolation.** One pin's failure must not abort the batch — catch it,
  record `success=False` with the error, and move on to the next pin.
- **R6 — Never raise.** A login/board-level exception → `{"posted_pins": [],
  "errors": [...]}`. (Global G1)
- **R7 — Description length cap.** Trim the composed description+hashtags to 500 chars
  for the Pinterest field.
- **R8 — Resilient selectors.** Use `find_element` with fallback selectors; a total
  selector failure logs a `[selector-miss]` warning into the run log. (Global G11)
- **R9 — Clean up temp files.** Always `os.unlink` the downloaded image after posting.

## Failure Handling

- Login / board creation failure → node-level error, empty `posted_pins`; the run
  still advances to `store_results` (which will find nothing successful to store).
- Single pin failure → recorded in that pin's `PostResult`, batch continues.

## Done / Success Criteria

`posted_pins` has one `PostResult` per attempted pin. `success=True` entries are the
ones the Memory Writer will persist. The Orchestrator's `posted` count = number of
`success=True`.

## Notes

Because this is the only side-effecting agent, it is also the one most bound by the
global platform-safety and dry-run rules. Treat every relaxation of R1/R2 as an
account-ban risk.
