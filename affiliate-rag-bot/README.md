# 🤖 Amazon → Pinterest RAG Affiliate Bot  v3

A production-grade affiliate marketing pipeline powered by **LangGraph**, **LangChain**, **OpenAI (gpt-5-nano)**, **PostgreSQL + pgvector RAG**, and **Playwright**.

---

## Architecture

```
START
  ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 1: scrape_amazon                                   │
│   Playwright logs into Amazon, scrapes Best Sellers     │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 2: search_trends                                   │
│   Tavily searches for real-time trending keywords       │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 3: rag_retrieve                                    │
│   pgvector finds similar past pins as few-shot context  │
│   (COLD START on first run — gets smarter over time)    │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 4+5: compose_pins   ← ONE structured LLM call      │
│   gpt-5-nano SELECTS the best products by commission   │
│   AND WRITES every pin (title/description/hashtags) in  │
│   a single schema-validated JSON response.              │
│   Trends + RAG context sent once · FTC auto-appended.   │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 6: get_affiliate_links                             │
│   Playwright calls Amazon SiteStripe API for each ASIN  │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 7: post_pinterest                                  │
│   Playwright posts each pin with human-like typing      │
│   20-minute delay between pins (anti-shadowban)         │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│ NODE 8: store_results  ← RAG FLYWHEEL                  │
│   Successful pins stored in pgvector for future runs    │
│   Bot gets smarter with every single run                │
└──────────────────────┬──────────────────────────────────┘
                       ↓
                      END
```

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Orchestration | **LangGraph** | Stateful agent pipeline with conditional edges |
| LLM | **OpenAI gpt-5-nano** (LangChain) | Product ranking + pin content generation |
| RAG Store | **pgvector** (PostgreSQL) | Pin memory + similarity search |
| Dedup ledger | **PostgreSQL** (`seen_products`) | Never re-pin the same product |
| Embeddings | **sentence-transformers** (local) | all-MiniLM-L6-v2 — no API key needed |
| Search | **Tavily** | Real-time trending keywords |
| Browser | **Playwright** (Python) | Amazon scraping + Pinterest posting |
| Monitoring | **LangSmith** (optional) | Visual trace of every graph run |
| Terminal UI | **Rich** | Live streaming CLI dashboard |
| Web API | **FastAPI + Uvicorn** | REST + WebSocket live run streaming |
| Web UI | **Tailwind CSS** (no build) | Mission-control dashboard |

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Fill in `.env`:

```env
AMAZON_EMAIL=you@gmail.com
AMAZON_PASSWORD=yourpassword
AMAZON_ASSOCIATE_TAG=karu8749-21   # ← Your tag from earlier!
AMAZON_MARKETPLACE=amazon.in

PINTEREST_EMAIL=you@gmail.com
PINTEREST_PASSWORD=yourpassword

OPENAI_API_KEY=sk-proj-...         # platform.openai.com/api-keys
OPENAI_MODEL=gpt-5-nano            # reasoning model; also sets LLM_REASONING_EFFORT=minimal
TAVILY_API_KEY=tvly-...            # Free at app.tavily.com (optional)

# PostgreSQL + pgvector (URL-encode special chars, e.g. @ -> %40)
DATABASE_URL=postgresql://postgres:password@localhost:5432/affiliate_rag_bot
```

### 1b. Provision the database (one time)

Create the project database and enable the `vector` extension (run as a Postgres
superuser, e.g. `postgres`):

```sql
CREATE DATABASE affiliate_rag_bot;
\c affiliate_rag_bot
CREATE EXTENSION IF NOT EXISTS vector;
```

The app auto-creates its tables (`seen_products` and the pgvector tables) on first
run — no migrations to run.

### 3. (Optional) Get a free Tavily API key

Tavily adds **real-time trending keywords** to captions, but it's **optional** —
the bot falls back to sensible static keywords when no key is set, and the
pipeline continues either way. Add one only if you want fresher trends:

1. Go to [app.tavily.com](https://app.tavily.com)
2. Sign up (free — 1000 searches/month)
3. Copy your API key → paste as `TAVILY_API_KEY`

---

## Running

### Option A — Web Dashboard (recommended)

A FastAPI server serves a clean mission-control dashboard: launch runs, watch
the 9 nodes execute live (WebSocket-streamed), and view stats, history, and a
setup checklist.

```bash
# Windows
venv\Scripts\python.exe -m uvicorn server:app --reload
# macOS / Linux
python -m uvicorn server:app --reload
```

Then open **http://127.0.0.1:8000**. The frontend uses Tailwind via CDN, so no
Node/npm build step is needed — but it does require internet to load Tailwind +
fonts on first paint.

### Option B — CLI

```bash
python main.py                    # standard run (home category)
python main.py --category fashion # different category
python main.py --dry-run          # no actual posting
```

Both the web dashboard and the CLI run the **same** pipeline (`pipeline_runner.py`).

---

## The RAG Flywheel Effect

On **first run**: the pgvector store is empty → gpt-5-nano generates content purely from product data + trends.

After **each run**: Every successfully-posted pin is stored in pgvector with its full content.

On **subsequent runs**: The RAG retriever finds similar past pins and injects them as few-shot examples, making every new pin better calibrated to your niche.

After **50+ runs**: The bot has a deep memory of what works in your category and generates increasingly optimised content automatically.

---

## Cron Schedule (recommended)

Post 1 pin every 3 hours = 8 pins/day (sweet spot for Pinterest SEO):

```bash
# Run every 3 hours (posts 1 product per run)
0 */3 * * * cd /path/to/affiliate-rag-bot && source venv/bin/activate && PRODUCTS_PER_RUN=1 python main.py >> logs/$(date +\%Y-\%m-\%d).log 2>&1
```

---

## Commission Rates (Amazon India)

| Category | Rate | Pinterest Fit |
|---|---|---|
| Fashion/Apparel | **9%** | ⭐⭐⭐⭐⭐ |
| Furniture/Home | **8%** | ⭐⭐⭐⭐⭐ |
| Kitchen | **7%** | ⭐⭐⭐⭐ |
| Beauty | **6%** | ⭐⭐⭐⭐ |
| Electronics | 2–5% | ⭐⭐ |
