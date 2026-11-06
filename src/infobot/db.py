"""Almacenamiento SQLite: tweets vistos, novedades, fichas y publicaciones."""

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
-- Una ficha = un tema (una promo, un TOTW, un SBC…) = un único mensaje en el grupo, que se completa con cada novedad
CREATE TABLE IF NOT EXISTS stories (
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
    message_ids_json TEXT NOT NULL DEFAULT '[]',
    dirty INTEGER NOT NULL DEFAULT 1,
    closed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

MAX_STORY_IMAGES = 9

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
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(items)")}
        if "story_id" not in cols:
            self.conn.execute("ALTER TABLE items ADD COLUMN story_id INTEGER")
        # Ya no hay "filtraciones": las fuentes son fiables y lo que no es oficial ni predicción va sin etiqueta
        self.conn.execute("UPDATE items SET source_type='none' WHERE source_type='leak'")
        self.conn.commit()

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
            " tweet_ids_json, images_json, created_at, story_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.kind, item.source_type, item.title, item.summary, item.details,
                json.dumps(item.key_facts, ensure_ascii=False), json.dumps(item.extra, ensure_ascii=False),
                json.dumps(item.tweet_ids), json.dumps(item.images), now_iso(), item.story_id,
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
        keys = r.keys()
        return Item(
            id=r["id"],
            story_id=r["story_id"] if "story_id" in keys else (r["id"] if "dirty" in keys else None),
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

    # --- fichas ---
    def save_story(self, story: Item) -> int:
        """Crea la ficha (si no tiene id) o la sustituye por su versión completa; queda pendiente de publicar."""
        values = (
            story.kind, story.source_type, story.title, story.summary, story.details,
            json.dumps(story.key_facts, ensure_ascii=False), json.dumps(story.extra, ensure_ascii=False),
            json.dumps(story.tweet_ids), json.dumps(story.images[:MAX_STORY_IMAGES]), now_iso(),
        )
        if story.id is None:
            cur = self.conn.execute(
                "INSERT INTO stories(kind, source_type, title, summary, details, key_facts_json, extra_json,"
                " tweet_ids_json, images_json, updated_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (*values, values[-1]),
            )
            story.id = cur.lastrowid
        else:
            self.conn.execute(
                "UPDATE stories SET kind=?, source_type=?, title=?, summary=?, details=?, key_facts_json=?,"
                " extra_json=?, tweet_ids_json=?, images_json=?, updated_at=?, dirty=1 WHERE id=?",
                (*values, story.id),
            )
        self.conn.commit()
        story.story_id = story.id
        return story.id

    def get_story(self, story_id: int) -> Item | None:
        row = self.conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def open_stories(self) -> list[Item]:
        rows = self.conn.execute("SELECT * FROM stories WHERE closed=0 ORDER BY updated_at DESC").fetchall()
        return [self._row_to_item(r) for r in rows]

    def close_story(self, story_id: int) -> None:
        self.conn.execute("UPDATE stories SET closed=1 WHERE id=?", (story_id,))
        self.conn.commit()

    def dirty_stories(self) -> list[Item]:
        rows = self.conn.execute("SELECT * FROM stories WHERE dirty=1 ORDER BY updated_at").fetchall()
        return [self._row_to_item(r) for r in rows]

    def story_message_ids(self, story_id: int) -> list[int]:
        row = self.conn.execute("SELECT message_ids_json FROM stories WHERE id=?", (story_id,)).fetchone()
        return json.loads(row["message_ids_json"]) if row else []

    def mark_story_published(self, story_id: int, message_ids: list[int]) -> None:
        self.conn.execute("UPDATE stories SET dirty=0, message_ids_json=? WHERE id=?",
                          (json.dumps(message_ids), story_id))
        self.add_post("story", message_ids, story_id)

    def stories_updated_since(self, since_iso: str) -> list[Item]:
        rows = self.conn.execute(
            "SELECT * FROM stories WHERE dirty=0 AND updated_at >= ? ORDER BY updated_at", (since_iso,)
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def story_updated_at(self, story_id: int) -> str | None:
        row = self.conn.execute("SELECT updated_at FROM stories WHERE id=?", (story_id,)).fetchone()
        return row["updated_at"] if row else None
