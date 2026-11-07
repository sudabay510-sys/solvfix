"""SQLite storage for SolvFix MVP (local file solvfix.db, override with SOLVFIX_DB)."""
import os, json, sqlite3
from flask import g
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audits(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT, address TEXT, phone TEXT, city TEXT,
  score INTEGER, results_json TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS fix_items(id INTEGER PRIMARY KEY, audit_id INTEGER NOT NULL, site TEXT, issue TEXT, steps TEXT, claim_url TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, platform TEXT, author TEXT, rating INTEGER, text TEXT,
  reply TEXT DEFAULT '', status TEXT DEFAULT 'draft', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS post_batches(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, business TEXT, btype TEXT, city TEXT, tone TEXT,
  month TEXT, posts_json TEXT, source TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
"""
def path(): return os.environ.get("SOLVFIX_DB", os.path.join(os.path.dirname(__file__), "solvfix.db"))
def get():
    if "db" not in g:
        g.db = sqlite3.connect(path()); g.db.row_factory = sqlite3.Row; g.db.executescript(SCHEMA)
    return g.db
def close(_=None):
    d = g.pop("db", None)
    if d: d.close()
def q(sql, args=(), one=False):
    cur = get().execute(sql, args); rows = cur.fetchall(); return (rows[0] if rows else None) if one else rows
def x(sql, args=()):
    cur = get().execute(sql, args); get().commit(); return cur.lastrowid
