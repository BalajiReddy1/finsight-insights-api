"""SQLite persistence. Three things survive a restart:

  llm_calls   one row per Gemini call: model, tokens, duration, repairs, user,
              date - this is both the cost log and the quota counter
  reports     metadata for every generated PDF (id, path, kind, created_at)
  watchlist   the tickers a user is following
"""

import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT,
    endpoint      TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    duration_ms   INTEGER,
    repairs       INTEGER NOT NULL DEFAULT 0,
    ok            INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    day           TEXT    NOT NULL          -- YYYY-MM-DD, for quota counting
);
CREATE INDEX IF NOT EXISTS idx_llm_user_day ON llm_calls (user_id, day);

CREATE TABLE IF NOT EXISTS reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    kind       TEXT NOT NULL,
    path       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    day        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    user_id    TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    label      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, symbol)
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
