"""Central configuration.

The OpenAI/LLM key lives in `.env` (never in the DB) per project policy.
Instagram account credentials and the optional News API key live in the
`rags` store (SQLite) and are editable from the frontend Settings panel.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---- Filesystem ----------------------------------------------------------
IMAGES_DIR = BASE_DIR / "images"
PREVIEWS_DIR = IMAGES_DIR / "previews"
DB_FILE = BASE_DIR / "posts.db"

IMAGES_DIR.mkdir(exist_ok=True)
PREVIEWS_DIR.mkdir(exist_ok=True)

# ---- LLM (key from .env only) -------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
# Hard ceiling so a runaway generation can never burn the budget.
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "2200"))

# ---- Public image hosting (GitHub raw) ----------------------------------
# Defaults here; can be overridden per-deploy via .env or the rags settings.
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "skarthik06").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "instagram_automation").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

# ---- Generation defaults (editable in UI) -------------------------------
NICHES = ("quotes", "news")
DEFAULT_POSTS_PER_BATCH = 3
DEFAULT_SLIDES_PER_POST = 4
MAX_POSTS_PER_BATCH = 6
MAX_SLIDES_PER_POST = 6

DEFAULT_HANDLE = os.getenv("IG_HANDLE", "sparkle06.exe").strip()
