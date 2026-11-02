"""SQLite storage: profile, memories, requests, plans, artifacts."""
import json
import os
import re
import sqlite3
import time
from contextlib import closing

DB_PATH = os.getenv("DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hackaiathon.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT DEFAULT '', about TEXT DEFAULT '', location TEXT DEFAULT '',
  interests TEXT DEFAULT '', updated_at REAL
);
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT 'fact', text TEXT NOT NULL,
  source TEXT DEFAULT 'user', weight REAL DEFAULT 1, created_at REAL
);
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, params TEXT, status TEXT, stage TEXT, error TEXT,
  mode TEXT DEFAULT 'live', note TEXT, research TEXT, sources TEXT,
  memories_used TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER, position INTEGER, body TEXT, chosen INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER, plan_id INTEGER, kind TEXT, title TEXT,
  status TEXT, error TEXT, content TEXT, completed TEXT DEFAULT '[]',
  xp_earned INTEGER DEFAULT 0, created_at REAL
);
"""

JSON_COLS = {"params", "research", "sources", "memories_used", "body", "content", "completed"}


def connect():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    with closing(connect()) as c:
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO profile (id, updated_at) VALUES (1, ?)", (time.time(),))
        c.commit()


def _row(r):
    d = dict(r)
    for k in list(d):
        if k in JSON_COLS and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def query(sql, args=()):
    with closing(connect()) as c:
        return [_row(r) for r in c.execute(sql, args).fetchall()]


def one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    with closing(connect()) as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def insert(table, **fields):
    cols = list(fields)
    vals = [json.dumps(fields[k]) if k in JSON_COLS else fields[k] for k in cols]
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    return execute(sql, vals)


def update(table, row_id, **fields):
    cols = list(fields)
    vals = [json.dumps(fields[k]) if k in JSON_COLS else fields[k] for k in cols]
    sql = f"UPDATE {table} SET {','.join(c + '=?' for c in cols)} WHERE id=?"
    execute(sql, vals + [row_id])


# ---------- profile ----------
def get_profile():
    return one("SELECT * FROM profile WHERE id=1")


def save_profile(name, about, location, interests):
    execute(
        "UPDATE profile SET name=?, about=?, location=?, interests=?, updated_at=? WHERE id=1",
        (name, about, location, interests, time.time()),
    )
    return get_profile()


# ---------- memory ----------
_STOP = set(
    "the and for with that this from have has are was were you your our can will but not "
    "about into want would like get got just very more some any".split()
)


def _tokens(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 and w not in _STOP}


def add_memory(text, kind="fact", source="user", weight=1.0):
    text = (text or "").strip()
    if not text:
        return None
    dup = one("SELECT id FROM memories WHERE lower(text)=lower(?)", (text,))
    if dup:
        return dup["id"]
    return insert("memories", kind=kind, text=text, source=source, weight=weight, created_at=time.time())


def search_memories(text, k=8):
    """Relevance (keyword overlap) + weight + recency. Small-scale RAG over memory."""
    mems = query("SELECT * FROM memories ORDER BY created_at DESC, id DESC")
    q = _tokens(text)
    scored = []
    for i, m in enumerate(mems):
        overlap = len(q & _tokens(m["text"]))
        recency = 1.0 / (1.0 + i / 5.0)
        scored.append((overlap * 2 + m["weight"] + recency, overlap, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, _, m in scored[:k]]
