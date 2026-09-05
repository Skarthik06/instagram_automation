# Business-SK — Stack / Orchestration

The deployment glue for the Business-SK platform. The application code lives in two
separate repositories; clone them **as siblings** next to this one, then run the stack
with the `docker-compose.yml` here.

## Layout

```
BUSINESS_SK/
├─ docker-compose.yml        # orchestrates all 4 services (this repo)
├─ initdb/                   # Postgres init (creates the affiliate DB)
├─ AUDIT.md                  # full build/change audit
├─ creative-system.html      # "The Still Set" creative-system playbook
├─ instagram_automation/     # → github.com/Skarthik06/business-sk           (JK real-estate + IG backend + frontend)
└─ affiliate-rag-bot/        # → github.com/Skarthik06/business-sk-affiliate  (SK Amazon-affiliate engine)
```

## Setup

```bash
# clone the three repos as siblings
git clone https://github.com/Skarthik06/business-sk-stack.git BUSINESS_SK
cd BUSINESS_SK
git clone https://github.com/Skarthik06/business-sk.git instagram_automation
git clone https://github.com/Skarthik06/business-sk-affiliate.git affiliate-rag-bot

# create the two .env files from their .env.example templates, then:
docker compose up -d --build
```

## Services

| Service | Port | Repo |
|---|---|---|
| frontend (Vite/React) | 3000 | business-sk |
| backend (IG publisher + Still Set renderer) | 8000 | business-sk |
| affiliate_backend (product discovery) | 8100 | business-sk-affiliate |
| db (Postgres + pgvector) | 5432 | — |

## Secrets

Never committed. Each service reads its own `.env` (see `.env.example` in each repo);
the IG token encryption key (`.ragskey`) is git-ignored and stays local.
