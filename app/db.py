"""SQLite layer: connection helper, schema, and published-post history.

A single DB file (`posts.db`) holds three concerns:
  - `accounts`        : Instagram accounts + their Graph API creds  (rags)
  - `app_settings`    : misc keys (News API key, hosting overrides) (rags)
  - `published_posts` : history of what was actually posted
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from app.settings import DB_FILE


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call repeatedly."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                label           TEXT NOT NULL,
                niche           TEXT NOT NULL DEFAULT 'quotes',
                ig_business_id  TEXT,
                ig_access_token TEXT,
                is_active       INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # Posted quote bodies, normalized, to avoid repeating quotes over time.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS used_quotes (
                norm       TEXT PRIMARY KEY,
                quote      TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS published_posts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id    INTEGER,
                account_label TEXT,
                niche         TEXT,
                caption       TEXT,
                media_type    TEXT,
                ig_media_id   TEXT,
                permalink     TEXT,
                cover_url     TEXT,
                slide_urls    TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )


# ===================== PUBLISHED POSTS =====================

def save_published_post(
    *,
    account_id: Optional[int],
    account_label: str,
    niche: str,
    caption: str,
    media_type: str,
    ig_media_id: Optional[str],
    permalink: Optional[str],
    cover_url: Optional[str],
    slide_urls: List[str],
) -> int:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO published_posts
                (account_id, account_label, niche, caption, media_type,
                 ig_media_id, permalink, cover_url, slide_urls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                account_label,
                niche,
                caption,
                media_type,
                ig_media_id,
                permalink,
                cover_url,
                json.dumps(slide_urls),
            ),
        )
        return int(cur.lastrowid)


def _row_to_post(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    try:
        d["slide_urls"] = json.loads(d.get("slide_urls") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["slide_urls"] = []
    return d


def get_published_posts(limit: int = 100, niche: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect() as conn:
        cur = conn.cursor()
        if niche:
            cur.execute(
                "SELECT * FROM published_posts WHERE niche = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (niche, limit),
            )
        else:
            cur.execute(
                "SELECT * FROM published_posts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_post(r) for r in cur.fetchall()]


def count_published_posts() -> int:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM published_posts")
        return int(cur.fetchone()[0])


# ===================== USED QUOTES (de-duplication) =====================

import re as _re


def normalize_quote(text: str) -> str:
    """Lowercase, strip punctuation/whitespace — for duplicate comparison."""
    return _re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()


def add_used_quotes(quotes: List[str]) -> None:
    rows = [(normalize_quote(q), q.strip()) for q in quotes if q and q.strip()]
    rows = [(n, q) for n, q in rows if n]
    if not rows:
        return
    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO used_quotes (norm, quote) VALUES (?, ?)", rows
        )


def get_recent_quote_texts(limit: int = 20) -> List[str]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT quote FROM used_quotes ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [r[0] for r in cur.fetchall()]


def get_used_quote_norms() -> set:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT norm FROM used_quotes")
        return {r[0] for r in cur.fetchall()}
