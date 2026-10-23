"""Orquestación: recoger → guardar → analizar → publicar → actualizar el estado."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import analyzer
from .config import DATA_DIR, MEDIA_DIR, OUT_DIR, Config
from .db import DB
from .media import download_media
from .models import Item, Tweet
from .render import telegram_format as fmt
from .render.cover import CoverRenderer, daily_cover_html, item_cover_html
from .state import expire, load_state, merge, save_state

log = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "infobot.db"
STATE_PATH = DATA_DIR / "state.json"
MAX_TWEET_AGE = timedelta(days=3)


def make_publisher(cfg: Config, dry_run: bool):
    if dry_run:
        from .outbox import Outbox

        return Outbox()
    from .telegram import Telegram

    return Telegram(cfg.telegram_token, cfg.telegram_channel)


# ---------- 1. Recoger ----------

def ingest(db: DB, cfg: Config, tweets: list[Tweet]) -> list[Tweet]:
    """Guarda los tweets nuevos. Los demasiado antiguos se guardan como 'ignored' para no publicarlos."""
    now = datetime.now(timezone.utc)
    first_run = db.get_meta("first_run_at") is None
    max_age = timedelta(hours=cfg.first_run_hours) if first_run else MAX_TWEET_AGE
    new: list[Tweet] = []
    known = db.known_ids([t.id for t in tweets])
    for t in sorted(tweets, key=lambda x: x.created_at):
        if t.id in known:
            continue
        created = t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)
        too_old = now - created > max_age
        db.add_tweet(t, status="ignored" if too_old else "pending")
        if not too_old:
            new.append(t)
    if first_run:
        db.set_meta("first_run_at", now.isoformat(timespec="seconds"))
    download_media(new)
    for t in new:
        db.set_local_media(t.id, t.local_media)
    log.info("Tweets nuevos: %d", len(new))
    return new


def ensure_media(db: DB, tweets: list[Tweet]) -> None:
    """En CI data/media no se guarda: si faltan imágenes de tweets pendientes, se vuelven a descargar."""
    missing = [t for t in tweets if t.media and not all((MEDIA_DIR / n).exists() for n in t.local_media or ["_"])]
    if missing:
        download_media(missing)
        for t in missing:
            db.set_local_media(t.id, t.local_media)


# ---------- 2. Analizar ----------

def recent_titles(db: DB, days: int = 4) -> list[str]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    rows = db.conn.execute("SELECT title FROM items WHERE created_at >= ? ORDER BY id", (since,)).fetchall()
    return [r["title"] for r in rows]


def analyze_pending(db: DB, cfg: Config, state: dict[str, Any]) -> list[Item]:
    pending = db.pending_tweets()
    if not pending:
        return []
    ensure_media(db, pending)
    created: list[Item] = []
    for batch, result, error in analyzer.analyze(cfg, pending, state, recent_titles(db)):
        if error is not None:
            db.bump_attempts([t.id for t in batch])
            continue
        items, ignored, missing = result
        for it in items:
            db.add_item(it)
            created.append(it)
        db.mark_tweets([i for it in items for i in it.tweet_ids], "done")
        db.mark_tweets(list(ignored), "ignored")
        if missing:
            log.warning("Claude no trató %d tweets; se reintentarán", len(missing))
            db.bump_attempts(list(missing))
    log.info("Novedades creadas: %d", len(created))
    return created


# ---------- 3. Publicar ----------

def _hydrate(db: DB, item: Item) -> None:
    tweets = db.get_tweets(item.tweet_ids)
    item.urls = [t.url for t in tweets]
    item.accounts = sorted({t.account for t in tweets})
    if any(not (MEDIA_DIR / n).exists() for n in item.images):
        download_media(tweets)


def publish_item(pub, renderer: CoverRenderer, item: Item, cfg: Config) -> list[int]:
    cover = renderer.render(item_cover_html(item, cfg.channel_title), OUT_DIR / "covers" / f"item_{item.id}.png")
    photos = [cover] + [MEDIA_DIR / n for n in item.images if (MEDIA_DIR / n).exists()][:9]
    text = fmt.item_message(item, cfg.show_source_link)
    ids = pub.send_album(photos, fmt.caption(item))
    for chunk in fmt.split_html(text):
        ids.append(pub.send_message(chunk, reply_to=ids[0]))
    return ids


def update_pinned(db: DB, pub, state: dict[str, Any], cfg: Config, dry_run: bool) -> None:
    html = fmt.pinned_message(state, cfg.channel_title)
    mid = db.get_meta("pinned_message_id")
    if mid and not dry_run:
        try:
            pub.edit_message(int(mid), html)
            return
        except Exception as e:  # noqa: BLE001 - p. ej. si alguien borró el mensaje
            log.warning("No se pudo editar el fijado (%s); se crea otro", e)
    new_id = pub.send_message(html)
    pub.pin(new_id)
    if not dry_run:
        db.set_meta("pinned_message_id", str(new_id))
        db.add_post("pinned", [new_id])


def run(cfg: Config, *, dry_run: bool = False, tweets: list[Tweet] | None = None,
        analysis_override: dict | None = None, db_path: Path = DB_PATH, state_path: Path = STATE_PATH) -> dict:
    """Ciclo completo. `tweets` y `analysis_override` permiten ejecutarlo con datos de ejemplo."""
    from .sources import fetch_all

    if dry_run:
        # En dry-run se trabaja sobre una copia: la base real no se toca.
        import shutil

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        copy = OUT_DIR / "dryrun.db"
        copy.unlink(missing_ok=True)
        if Path(db_path).exists():
            shutil.copy(db_path, copy)
        db_path = copy
    db = DB(db_path)
    state = expire(load_state(state_path), tz=cfg.timezone)
    pub = make_publisher(cfg, dry_run)
    summary = {"fetched": 0, "new": 0, "items": 0, "posted": 0}
    try:
        fetched = tweets if tweets is not None else fetch_all(cfg)
        summary["fetched"] = len(fetched)
        summary["new"] = len(ingest(db, cfg, fetched))

        if analysis_override is not None:
            original = analyzer.call_claude
            analyzer.call_claude = lambda *a, **k: analysis_override
            try:
                summary["items"] = len(analyze_pending(db, cfg, state))
            finally:
                analyzer.call_claude = original
        else:
            summary["items"] = len(analyze_pending(db, cfg, state))

        to_post = db.unposted_items()
        if to_post:
            with CoverRenderer() as renderer:
                for item in to_post:
                    _hydrate(db, item)
                    ids = publish_item(pub, renderer, item, cfg)
                    if not dry_run:
                        db.mark_item_posted(item.id, ids)
                    state = merge(state, item, cfg.timezone)
                    summary["posted"] += 1
            if not dry_run:
                save_state(state_path, state)
            update_pinned(db, pub, state, cfg, dry_run)
        elif not dry_run and not state_path.exists():
            save_state(state_path, state)
    finally:
        if dry_run:
            path = pub.write_html()
            log.info("Vista previa: %s", path)
            summary["preview"] = str(path)
        db.close()
    log.info("Resumen: %s", json.dumps(summary))
    return summary


def daily(cfg: Config, *, dry_run: bool = False, db_path: Path = DB_PATH, force: bool = False) -> dict:
    db = DB(db_path)
    pub = make_publisher(cfg, dry_run)
    try:
        now = datetime.now(timezone.utc)
        last = db.get_meta("last_daily_at")
        if last and not force and now - datetime.fromisoformat(last) < timedelta(hours=20):
            return {"daily": "ya enviado"}
        items = db.items_since((now - timedelta(hours=24)).isoformat(timespec="seconds"))
        if not items:
            return {"daily": "sin novedades"}
        label = datetime.now(ZoneInfo(cfg.timezone)).strftime("%d/%m/%Y")
        with CoverRenderer() as r:
            cover = r.render(daily_cover_html(items, cfg.channel_title, label), OUT_DIR / "covers" / "daily.png")
        ids = [pub.send_photo(cover, f"🗞️ <b>Resumen del día · {label}</b>")]
        for chunk in fmt.split_html(fmt.daily_message(items, label)):
            ids.append(pub.send_message(chunk, reply_to=ids[0]))
        if not dry_run:
            db.set_meta("last_daily_at", now.isoformat(timespec="seconds"))
            db.add_post("daily", ids)
        return {"daily": len(items)}
    finally:
        if dry_run:
            pub.write_html("InfoBot FC 27 — resumen diario")
        db.close()
