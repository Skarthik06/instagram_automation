# utils/db.py
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "posts.db")

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote TEXT UNIQUE,
            image_url TEXT,
            posted_at TEXT DEFAULT (datetime('now'))
        )
    """)
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
