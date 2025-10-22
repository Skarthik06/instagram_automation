# utils/db.py (simplified/reverted)
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "posts.db")


def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()


def get_all_quotes():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT quote FROM posts")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_post(quote, image_url):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO posts (quote, image_url) VALUES (?, ?)", (quote, image_url))
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
    return [{"id": r[0], "quote": r[1], "image_url": r[2], "posted_at": r[3]} for r in rows]


def get_latest_post():
    posts = get_posts(limit=1)
    return posts[0] if posts else None
