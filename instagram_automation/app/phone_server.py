"""Business-SK PHONE server — Option A (smart split), the light always-on half.

This is the 24/7 engagement half that runs on the OPPO F17 Pro (Termux / proot Ubuntu):
    Meta webhook  →  comment/DM event  →  deterministic rules  →  reply + product-card DM
It mounts ONLY the engagement + webhook routers, so it NEVER imports the heavy
content-generation dependencies (torch, transformers, playwright, chromium, rembg,
onnxruntime, docling) that stay on the PC. The application logic is UNCHANGED — this is
purely a slim runtime entrypoint that reuses app/engagement/* (no redesign).

Run:
    uvicorn app.phone_server:app --host 0.0.0.0 --port 8000

Env (see .env.phone.example):
    DATABASE_URL                 local Postgres on the phone (instagram_business)
    ENGAGEMENT_LIVE=1            actually send replies/DMs (0 = dry-run)
    META_WEBHOOK_VERIFY_TOKEN    the token you set in the Meta webhook config
    META_APP_SECRET              Meta app secret (verifies webhook signatures)
    ENGAGEMENT_AUTO_SYNC=0       webhooks are primary; 1 + a large SYNC_INTERVAL adds a
                                 light fallback poll (e.g. 300s) if you want a safety net
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Engagement + webhook routers (light imports only: rags, settings, rules, service, store, openai).
from app.engagement.api import router as engagement_router
from app.engagement.api import webhook_router, start_background_sync


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Webhooks (push) are the primary, rate-limit-free path. start_background_sync() is a
    # no-op unless ENGAGEMENT_AUTO_SYNC=1 — set a large ENGAGEMENT_SYNC_INTERVAL (e.g. 300)
    # if you want an occasional fallback poll in addition to webhooks.
    start_background_sync()
    yield


app = FastAPI(title="Business-SK Engagement (phone)", lifespan=lifespan)
app.include_router(engagement_router)
app.include_router(webhook_router)


@app.get("/healthz")
def healthz():
    """Cheap liveness probe (no DB hit) for uptime checks + the boot script."""
    return {
        "status": "ok",
        "role": "phone-engagement",
        "live": os.getenv("ENGAGEMENT_LIVE", "0") not in ("0", "false", ""),
        "auto_sync": os.getenv("ENGAGEMENT_AUTO_SYNC", "1") not in ("0", "false", ""),
    }
