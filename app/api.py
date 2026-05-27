"""FastAPI application — the single backend entrypoint.

Run:  uvicorn app.api:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, rags, settings
from app.schemas import (
    AccountIn,
    AccountUpdate,
    GenerateRequest,
    PublishRequest,
    SettingsIn,
)
from app.services import generator, news
from app.services.instagram import InstagramError
from app.services.llm import LLMError


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    rags.seed_from_env()
    yield


app = FastAPI(title="Instagram Automation", version="4.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve locally-rendered previews (before they are pushed to GitHub on publish).
app.mount("/cdn", StaticFiles(directory=str(settings.IMAGES_DIR)), name="cdn")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "openai_key_set": bool(settings.OPENAI_API_KEY),
        "model": settings.OPENAI_MODEL,
        "niches": list(settings.NICHES),
    }


# ===================== ACCOUNTS (rags) =====================

@app.get("/api/accounts")
def list_accounts(niche: str | None = None, active_only: bool = False):
    return {"accounts": rags.list_accounts(niche=niche, active_only=active_only)}


@app.post("/api/accounts")
def create_account(body: AccountIn):
    return rags.add_account(
        label=body.label, handle=body.handle, niche=body.niche,
        ig_business_id=body.ig_business_id, ig_access_token=body.ig_access_token,
        is_active=body.is_active,
    )


@app.put("/api/accounts/{account_id}")
def update_account(account_id: int, body: AccountUpdate):
    updated = rags.update_account(account_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, "Account not found")
    return updated


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    if not rags.delete_account(account_id):
        raise HTTPException(404, "Account not found")
    return {"deleted": account_id}


# ===================== SETTINGS (rags) =====================

@app.get("/api/settings")
def get_settings():
    return rags.get_public_settings()


@app.put("/api/settings")
def update_settings(body: SettingsIn):
    for key, value in body.model_dump(exclude_none=True).items():
        rags.set_setting(key, str(value))
    return rags.get_public_settings()


# ===================== GENERATION =====================

@app.post("/api/generate")
async def generate(body: GenerateRequest):
    try:
        return await generator.generate(
            niche=body.niche, posts=body.posts, slides=body.slides, topic=body.topic
        )
    except LLMError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))


@app.get("/api/batch/{batch_id}")
def get_batch(batch_id: str):
    batch = generator.get_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found or expired")
    return batch


@app.post("/api/publish")
def publish(body: PublishRequest):
    try:
        result = generator.publish(
            batch_id=body.batch_id, post_index=body.post_index, account_id=body.account_id
        )
        return {"success": True, **result}
    except InstagramError as exc:
        print(f"[publish] Instagram error: {exc}")  # visible in the server terminal
        raise HTTPException(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(exc))


# ===================== NEWS PREVIEW (optional helper) =====================

@app.get("/api/news")
def preview_news(topic: str | None = None, limit: int = 8):
    return {"items": news.fetch_news(topic=topic, limit=limit)}


# ===================== HISTORY / STATS =====================

@app.get("/api/posts")
def posts(limit: int = 50, niche: str | None = None):
    return {"posts": db.get_published_posts(limit=limit, niche=niche)}


@app.get("/api/stats")
def stats():
    all_posts = db.get_published_posts(limit=1000)
    by_niche = {"quotes": 0, "news": 0}
    for p in all_posts:
        if p["niche"] in by_niche:
            by_niche[p["niche"]] += 1
    return {
        "total_posts": len(all_posts),
        "by_niche": by_niche,
        "accounts": len(rags.list_accounts()),
        "recent": all_posts[:6],
    }


if __name__ == "__main__":
    import uvicorn

    # Bind to localhost only — the API is for this machine, not the network.
    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=True)
