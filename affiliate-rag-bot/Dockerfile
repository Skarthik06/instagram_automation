# ---------------------------------------------------------------------------
# affiliate-rag-bot — backend (FastAPI JSON API + LangGraph pipeline)
# ---------------------------------------------------------------------------
# Python 3.12 for guaranteed wheels (torch, numpy, pgvector, playwright, …).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HEADLESS=true \
    # Cache the local embedding model here (persisted via a volume in compose).
    HF_HOME=/root/.cache/huggingface

WORKDIR /app

# ---- System dependencies -------------------------------------------------
#  git / ca-certificates -> pip VCS + TLS. Playwright's own system libs are
#  installed by `playwright install --with-deps chromium` below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# ---- CPU-only torch first (sentence-transformers pulls torch) ------------
# The default torch wheel is the multi-GB CUDA build; the CPU index keeps the
# image ~2GB smaller. Installed before requirements so the resolver reuses it.
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch

# ---- Python dependencies (cached layer) ----------------------------------
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Playwright chromium + system libs (Amazon Best Sellers scraper) -----
RUN playwright install --with-deps chromium

# ---- Pre-fetch the free local embedding model (all-MiniLM-L6-v2, ~80MB) --
# Bakes it into the image so the first RAG request isn't slow/offline.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || true

# ---- Application code -----------------------------------------------------
COPY . .

EXPOSE 8100

# Bind to all interfaces inside the container network (compose maps :8100).
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100"]
