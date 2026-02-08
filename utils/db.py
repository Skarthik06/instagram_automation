# utils/db.py
import sqlite3
import os
from typing import Optional, Dict

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "posts.db")


# ===================== DB INIT =====================

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Existing posts table (UNCHANGED)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote TEXT UNIQUE,
            image_url TEXT,
            posted_at TEXT DEFAULT (datetime('now'))
        )
        """
    )

    # ✅ NEW: LLM CACHE TABLE
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote TEXT UNIQUE,
            caption TEXT,
            hashtags TEXT,
            image_prompt TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )

    conn.commit()
    conn.close()


# ===================== POSTS =====================

def get_all_quotes():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT quote FROM posts")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_post(quote: str, image_url: str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO posts (quote, image_url) VALUES (?, ?)",
        (quote, image_url),
    )
    conn.commit()
    conn.close()


def get_posts(limit: int = 100):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, quote, image_url, posted_at FROM posts ORDER BY posted_at DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "quote": r[1], "image_url": r[2], "posted_at": r[3]}
        for r in rows
    ]


def get_latest_post():
    posts = get_posts(limit=1)
    return posts[0] if posts else None


# ===================== LLM CACHE =====================

def get_cached_llm_bundle() -> Optional[Dict]:
    """
    Returns the most recent cached Gemini output if available.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT quote, caption, hashtags, image_prompt
        FROM llm_cache
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "quote": row[0],
        "caption": row[1],
        "hashtags": row[2],
        "image_prompt": row[3],
    }


def save_llm_bundle(
    quote: str,
    caption: str,
    hashtags: str,
    image_prompt: str,
):
    """
    Save Gemini output so we don't call the API again.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO llm_cache
        (quote, caption, hashtags, image_prompt)
        VALUES (?, ?, ?, ?)
        """,
        (quote, caption, hashtags, image_prompt),
    )
    conn.commit()
    conn.close()
