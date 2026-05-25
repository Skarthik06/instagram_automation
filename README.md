# Instagram Autopilot — Studio

A production Instagram carousel generator + multi-account publisher for **two niches**:

- **Quotes** — original motivational quote carousels on scraped aesthetic backgrounds.
- **News** — live-headline carousels rendered as clean **infographics**.

One **Generate** click produces a *batch* of multi-slide carousel posts from a **single LLM call** (OpenAI `gpt-4o-mini`). You review them in the Studio and publish any post to any linked Instagram account.

---

## Architecture

```
app/
  settings.py            paths, env (OPENAI_API_KEY), defaults
  db.py                  SQLite connection + schema + post history
  rags.py                the "rags" store — accounts + keys CRUD
  schemas.py             pydantic request/response models
  services/
    emojis.py            data-driven emoji picker (emoji pkg, no hardcoded map)
    llm.py               OpenAI gpt-4o-mini — ONE batched JSON call + token usage
    news.py              Google-News RSS / optional News API
    scraper.py           Pinterest background scraper (ranked, watermark-filtered)
    render.py            carousel slide renderer (quote overlays + news infographics)
    hosting.py           GitHub-raw public hosting (push only at publish time)
    instagram.py         multi-account single + CAROUSEL publish (Graph API)
    generator.py         orchestrates: niche -> batch of carousels -> publish
  api.py                 FastAPI app (uvicorn app.api:app)
frontend/                React + Vite + Tailwind dashboard (Studio / Settings / History)
```

The legacy single-file scripts (`backend_api.py`, `main.py`, `llm_quote_gen.py`,
`ig_api_poster.py`, `playwright_scraper.py`, `utils/`) are **superseded** by the
`app/` package and can be deleted.

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
playwright install chromium      # for the Quotes background scraper

cd frontend
npm install
```

### Keys

| Key | Where it lives | Why |
| --- | --- | --- |
| `OPENAI_API_KEY` | **`.env`** | LLM key — kept out of the DB on purpose |
| Instagram accounts (business id + token) | **rags store** (Settings panel) | per-account, masked, never committed |
| News API key (optional) | **rags store** (Settings panel) | blank = free Google-News RSS |
| GitHub hosting (`user`/`repo`/`branch`) | `.env` or Settings panel | public image hosting for Instagram |

Copy `.env.example` to `.env` and paste your `OPENAI_API_KEY`. Add your Instagram
account(s) from the **Settings** tab in the UI (an existing `.env` IG account is
auto-migrated on first run).

### Run

```bash
# terminal 1 — backend
venv\Scripts\activate
uvicorn app.api:app --reload --port 8000

# terminal 2 — frontend
cd frontend && npm run dev      # http://localhost:3000
```

---

## How generation works (and stays cheap)

1. **News only:** fetch live headlines (RSS or News API) as factual grounding.
2. **One LLM call** turns the whole batch into structured JSON — every post's
   slides, caption, and hashtags at once.
3. **Quotes:** scrape + rank aesthetic backgrounds; overlay the quote text.
   **News:** render gradient infographic slides (no scraping, no hallucinated facts).
4. Slides are saved locally and shown as previews (no git push yet).
5. On **Publish**, only the chosen post's slides are pushed to the public GitHub
   repo (for hostable URLs) and posted as a carousel to the selected account.

### Token economics (input : output)

`gpt-4o-mini` bills **input and output tokens separately, and output costs ~4x input**
(~$0.15 vs ~$0.60 per 1M tokens). So the cheapest design **minimizes repeated input
and keeps output tight**:

- **One batched call, not N.** The instructions + JSON schema (the fixed *input*
  overhead) are sent **once** for the entire batch. Generating each post in its own
  call would resend that overhead every time — for a 3-post batch that's ~3x the
  wasted input.
- **Output is capped** by `LLM_MAX_OUTPUT_TOKENS` (default 2200) as a hard cost ceiling.
- **News facts come from RSS, not the model**, so the model only *rewrites* short text
  rather than generating long content — less output spent.

After every generation the Studio shows the real numbers from the API:

```
input 612   output 1180   total 1792   in:out 0.52:1
```

The **in:out ratio** is `prompt_tokens / completion_tokens`. Because output is the
expensive side, a run that is output-heavy (low ratio) costs more per post than an
input-heavy one. Batching pushes more of the spend onto the cheap input side and
amortizes it across all posts, which is exactly what this pipeline is tuned for.

> Approx cost of one 3x4 batch is a few hundredths of a US cent. The cap guarantees a
> worst-case ceiling no matter what the model returns.

---

## Quotes quality controls (carried over from the original)

- **No repeated quotes.** Posted quote bodies are stored (`used_quotes` table). Each
  generation passes a bounded list of your recent quotes to the model as "do not
  reuse", and an exact-match guard drops any duplicate slide before rendering.
- **Brand hashtags.** A *Fixed / brand hashtags* field (Settings) is appended to every
  caption on top of the LLM hashtags. Blank falls back to `config.json` → `hashtags.fixed`.
- **Quote in the caption.** For the Quotes niche the lead slide quote is quoted at the
  top of the caption, then the LLM caption, then the hashtags.
- **`config.json`** (optional, advanced) tunes overlay look (`darkness`, `position`,
  `text_color`, `handle`), quote word limits, dedup depth, and hashtag count. Edits
  apply on the next generation — no restart needed.

## Emojis

No hardcoded emoji map. `app/services/emojis.py` resolves emojis at runtime from the
`emoji` library's full alias catalogue, with a small *concept -> alias* synonym layer
(e.g. `success -> trophy`, `growth -> chart_with_upwards_trend`). Captions get
contextually-chosen emojis automatically; slide text is kept emoji-free for clean overlays.

## Credential safety

- `.env` and `*.db` are git-ignored and untracked — the hosting `git push` can never
  sweep them up (it stages only the explicit slide image paths).
- IG tokens are **masked** in every API response; full values are read only by the publisher.
- The OpenAI key is read from `.env`, never written to the DB, never sent to the frontend.
- CORS is restricted to localhost.
