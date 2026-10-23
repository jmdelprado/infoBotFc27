"""Almacenamiento SQLite: tweets vistos, novedades y publicaciones."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Item, Tweet

SCHEMA = """
CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    url TEXT NOT NULL,
    media_json TEXT NOT NULL DEFAULT '[]',
    local_media_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL,
    key_facts_json TEXT NOT NULL,
    extra_json TEXT NOT NULL,
    tweet_ids_json TEXT NOT NULL,
    images_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    posted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER,
    kind TEXT NOT NULL,
    message_ids_json TEXT NOT NULL,
    posted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

MAX_ATTEMPTS = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- meta ---
    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    # --- tweets ---
    def add_tweet(self, t: Tweet, status: str = "pending") -> bool:
        """Guarda un tweet nuevo. Devuelve False si ya existía."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO tweets(id, account, created_at, text, url, media_json, status, fetched_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (t.id, t.account, t.created_at.isoformat(), t.text, t.url, json.dumps(t.media), status, now_iso()),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def known_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        q = ",".join("?" * len(ids))
        return {r["id"] for r in self.conn.execute(f"SELECT id FROM tweets WHERE id IN ({q})", ids)}

    def set_local_media(self, tweet_id: str, paths: list[str]) -> None:
        self.conn.execute("UPDATE tweets SET local_media_json=? WHERE id=?", (json.dumps(paths), tweet_id))
        self.conn.commit()

    def pending_tweets(self) -> list[Tweet]:
        rows = self.conn.execute(
            "SELECT * FROM tweets WHERE status='pending' AND attempts < ? ORDER BY created_at", (MAX_ATTEMPTS,)
        ).fetchall()
        return [self._row_to_tweet(r) for r in rows]

    def get_tweets(self, ids: list[str]) -> list[Tweet]:
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        rows = self.conn.execute(f"SELECT * FROM tweets WHERE id IN ({q})", ids).fetchall()
        return [self._row_to_tweet(r) for r in rows]

    @staticmethod
    def _row_to_tweet(r: sqlite3.Row) -> Tweet:
        return Tweet(
            id=r["id"],
            account=r["account"],
            created_at=datetime.fromisoformat(r["created_at"]),
            text=r["text"],
            url=r["url"],
            media=json.loads(r["media_json"]),
            local_media=json.loads(r["local_media_json"]),
        )

    def mark_tweets(self, ids: list[str], status: str) -> None:
        self.conn.executemany("UPDATE tweets SET status=? WHERE id=?", [(status, i) for i in ids])
        self.conn.commit()

    def bump_attempts(self, ids: list[str]) -> None:
        self.conn.executemany("UPDATE tweets SET attempts = attempts + 1 WHERE id=?", [(i,) for i in ids])
        self.conn.execute("UPDATE tweets SET status='failed' WHERE status='pending' AND attempts >= ?", (MAX_ATTEMPTS,))
        self.conn.commit()

    # --- items ---
    def add_item(self, item: Item) -> int:
        cur = self.conn.execute(
            "INSERT INTO items(kind, source_type, title, summary, details, key_facts_json, extra_json,"
            " tweet_ids_json, images_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                item.kind, item.source_type, item.title, item.summary, item.details,
                json.dumps(item.key_facts, ensure_ascii=False), json.dumps(item.extra, ensure_ascii=False),
                json.dumps(item.tweet_ids), json.dumps(item.images), now_iso(),
            ),
        )
        self.conn.commit()
        item.id = cur.lastrowid
        return item.id

    def unposted_items(self) -> list[Item]:
        rows = self.conn.execute("SELECT * FROM items WHERE posted=0 ORDER BY id").fetchall()
        return [self._row_to_item(r) for r in rows]

    def items_since(self, since_iso: str) -> list[Item]:
        rows = self.conn.execute(
            "SELECT * FROM items WHERE posted=1 AND created_at >= ? ORDER BY id", (since_iso,)
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    @staticmethod
    def _row_to_item(r: sqlite3.Row) -> Item:
        return Item(
            id=r["id"],
            kind=r["kind"],
            source_type=r["source_type"],
            title=r["title"],
            summary=r["summary"],
            details=r["details"],
            key_facts=json.loads(r["key_facts_json"]),
            extra=json.loads(r["extra_json"]),
            tweet_ids=json.loads(r["tweet_ids_json"]),
            images=json.loads(r["images_json"]),
        )

    def mark_item_posted(self, item_id: int, message_ids: list[int]) -> None:
        self.conn.execute("UPDATE items SET posted=1 WHERE id=?", (item_id,))
        self.add_post("item", message_ids, item_id)

    def add_post(self, kind: str, message_ids: list[int], item_id: int | None = None) -> None:
        self.conn.execute(
            "INSERT INTO posts(item_id, kind, message_ids_json, posted_at) VALUES (?,?,?,?)",
            (item_id, kind, json.dumps(message_ids), now_iso()),
        )
        self.conn.commit()
