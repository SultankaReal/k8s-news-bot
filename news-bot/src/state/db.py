"""SQLite-backed deduplication and article state store."""
import sqlite3
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ..config import get_config


def _db_path() -> str:
    return get_config().db_path


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS seen_articles (
                id      TEXT PRIMARY KEY,
                url     TEXT NOT NULL,
                title   TEXT,
                source  TEXT,
                seen_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_articles (seen_at);

            CREATE TABLE IF NOT EXISTS sent_digests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT NOT NULL,   -- 'daily' | 'weekly'
                sent_at    TEXT NOT NULL,
                article_count INTEGER
            );
        """)


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def is_seen(url: str) -> bool:
    aid = article_id(url)
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM seen_articles WHERE id = ?", (aid,)
        ).fetchone()
        return row is not None


def mark_seen(url: str, title: str = "", source: str = "") -> None:
    aid = article_id(url)
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO seen_articles (id, url, title, source, seen_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (aid, url, title, source, datetime.utcnow().isoformat()),
        )


def cleanup_old(ttl_days: int | None = None) -> int:
    ttl = ttl_days or get_config().article_ttl_days
    cutoff = (datetime.utcnow() - timedelta(days=ttl)).isoformat()
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM seen_articles WHERE seen_at < ?", (cutoff,)
        )
        return cur.rowcount


def log_digest(digest_type: str, article_count: int) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO sent_digests (type, sent_at, article_count) VALUES (?, ?, ?)",
            (digest_type, datetime.utcnow().isoformat(), article_count),
        )
