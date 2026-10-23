"""Orquestación: recoger → guardar → analizar → publicar → actualizar el estado."""

from __future__ import annotations

import hashlib
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
from .models import TOPIC_INTROS, TOPICS, Item, Tweet, topic_for
from .render import telegram_format as fmt
from .render.calendar import calendar_html, calendar_text
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

class Sections:
    """Secciones (temas) del grupo. Se crean la primera vez y sus ids se guardan en la base.
    Si el chat no tiene temas (canal normal), todo va al hilo principal."""

    def __init__(self, db: DB, pub, dry_run: bool):
        self.db, self.pub, self.dry_run = db, pub, dry_run
        self.ids: dict[str, int] = json.loads(db.get_meta("topics") or "{}")
        try:
            self.forum = pub.is_forum()
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo saber si el chat tiene temas: %s", e)
            self.forum = False

    def thread(self, key: str) -> int | None:
        if not self.forum:
            return None
        if key not in self.ids:
            meta = TOPICS[key]
            self.ids[key] = self.pub.create_topic(meta["name"], meta.get("icon_color"))
            log.info("Sección creada: %s", meta["name"])
            intro = TOPIC_INTROS.get(key)
            if intro:
                try:
                    self.pub.send_message(f"<b>{meta['name']}</b>\n\n{intro}", thread=self.ids[key])
                except Exception as e:  # noqa: BLE001
                    log.warning("No se pudo publicar la introducción de %s: %s", key, e)
            if not self.dry_run:
                self.db.set_meta("topics", json.dumps(self.ids))
        return self.ids[key]

    def send(self, key: str, fn, *args, **kwargs):
        """Envía en la sección `key`; si alguien borró la sección, la vuelve a crear y reintenta."""
        try:
            return fn(*args, thread=self.thread(key), **kwargs)
        except Exception as e:  # noqa: BLE001
            if "thread not found" not in str(e).lower():
                raise
            log.warning("La sección %s ya no existe; se vuelve a crear", key)
            self.ids.pop(key, None)
            return fn(*args, thread=self.thread(key), **kwargs)


def _hydrate(db: DB, item: Item) -> None:
    tweets = db.get_tweets(item.tweet_ids)
    item.urls = [t.url for t in tweets]
    item.accounts = sorted({t.account for t in tweets})
    if any(not (MEDIA_DIR / n).exists() for n in item.images):
        download_media(tweets)


def publish_item(pub, renderer: CoverRenderer, item: Item, cfg: Config, sections: Sections) -> list[int]:
    """Filtraciones: portada + imágenes + texto en la sección de su tipo.
    Lo oficial no se publica como mensaje: solo entra en el calendario (devuelve [])."""
    key = topic_for(item.kind, item.source_type)
    if key is None:
        return []
    cover = renderer.render(item_cover_html(item, cfg.channel_title), OUT_DIR / "covers" / f"item_{item.id}.png")
    photos = [cover] + [MEDIA_DIR / n for n in item.images if (MEDIA_DIR / n).exists()][:9]
    ids = sections.send(key, pub.send_album, photos, fmt.caption(item))
    for chunk in fmt.split_html(fmt.item_message(item, cfg.show_source_link)):
        ids.append(sections.send(key, pub.send_message, chunk, reply_to=ids[0]))
    return ids


def _edit_or_send(db: DB, meta_key: str, dry_run: bool, edit, send) -> None:
    """Edita el mensaje guardado en `meta_key`; si no existe o falla, envía uno nuevo."""
    mid = db.get_meta(meta_key)
    if mid and not dry_run:
        try:
            edit(int(mid))
            return
        except Exception as e:  # noqa: BLE001 - p. ej. si alguien borró el mensaje
            log.warning("No se pudo editar %s (%s); se crea otro", meta_key, e)
    new_id = send()
    if not dry_run:
        db.set_meta(meta_key, str(new_id))


def update_pinned(db: DB, pub, state: dict[str, Any], cfg: Config, dry_run: bool) -> None:
    """Estado actual, fijado en la sección General."""
    html = fmt.pinned_message(state, cfg.channel_title)

    def send() -> int:
        mid = pub.send_message(html)
        pub.pin(mid)
        return mid

    _edit_or_send(db, "pinned_message_id", dry_run, lambda mid: pub.edit_message(mid, html), send)


def update_calendar(db: DB, pub, renderer: CoverRenderer, sections: Sections, state: dict[str, Any],
                    cfg: Config, dry_run: bool) -> bool:
    """Calendario oficial de las próximas 2 semanas. Cuando su contenido cambia se publica de nuevo
    (imagen + lista) en la sección Calendario, se fija y se borra la versión anterior."""
    text = calendar_text(state, cfg.timezone)
    # Firma sin la línea "Actualizado" ni el día: cambia si cambia el contenido o al pasar de día (se mueve la ventana)
    today = datetime.now(ZoneInfo(cfg.timezone)).strftime("%Y-%m-%d")
    signature = hashlib.sha1((today + "\n".join(text.split("\n")[2:])).encode()).hexdigest()
    if not dry_run and db.get_meta("calendar_hash") == signature and db.get_meta("calendar_photo_id"):
        return False
    html, _ = calendar_html(state, cfg.channel_title, cfg.timezone)
    img = renderer.render(html, OUT_DIR / "covers" / "calendar.png", full_page=True, width=1600)
    caption = "📅 <b>Calendario oficial FC 27</b> · próximas 2 semanas\n✅ Solo lo que ya está en el juego o ha confirmado EA"

    old_ids = [db.get_meta("calendar_photo_id"), db.get_meta("calendar_text_id")]
    photo_id = sections.send("calendar", pub.send_photo, img, caption)
    text_ids = [sections.send("calendar", pub.send_message, chunk, reply_to=photo_id)
                for chunk in fmt.split_html(text)]
    try:
        pub.pin(photo_id)
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo fijar el calendario: %s", e)
    if not dry_run:
        for mid in old_ids:
            if mid:
                try:
                    pub.delete_message(int(mid))
                except Exception as e:  # noqa: BLE001 - p. ej. ya borrado a mano
                    log.info("No se pudo borrar el calendario anterior (%s): %s", mid, e)
        db.set_meta("calendar_photo_id", str(photo_id))
        db.set_meta("calendar_text_id", str(text_ids[0]))
        db.set_meta("calendar_hash", signature)
        db.add_post("calendar", [photo_id, *text_ids])
    return True


def update_evo_calendar(db: DB, pub, renderer: CoverRenderer, sections: Sections, state: dict[str, Any],
                        cfg: Config, dry_run: bool) -> bool:
    """Calendario de evoluciones (FUT.GG). Se republica cuando cambian las evoluciones o el día."""
    from .render.evo_calendar import evo_calendar_html, evo_calendar_text, evo_signature
    from .sources.futgg_evolutions import fetch_evolutions

    try:
        evos = fetch_evolutions(cfg.timezone)
        state["evolutions_feed"] = evos
    except Exception as e:  # noqa: BLE001 - si FUT.GG falla, se mantiene lo último conocido
        log.warning("No se pudieron leer las evoluciones de FUT.GG: %s", e)
        evos = state.get("evolutions_feed") or []
        if not evos:
            return False
    signature = evo_signature(evos, cfg.timezone)
    if not dry_run and db.get_meta("evocal_hash") == signature and db.get_meta("evocal_photo_id"):
        return False
    html, _ = evo_calendar_html(evos, cfg.channel_title, cfg.timezone)
    img = renderer.render(html, OUT_DIR / "covers" / "evo_calendar.png", full_page=True, width=1900)
    caption = "📆 <b>Calendario de evoluciones</b> · próximos 30 días\n⭐ VIP = pase premium"
    old_ids = json.loads(db.get_meta("evocal_message_ids") or "[]")
    photo_id = sections.send("evocal", pub.send_photo, img, caption)
    text_ids = [sections.send("evocal", pub.send_message, chunk, reply_to=photo_id)
                for chunk in fmt.split_html(evo_calendar_text(evos, cfg.timezone))]
    try:
        pub.pin(photo_id)
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo fijar el calendario de evoluciones: %s", e)
    if not dry_run:
        for mid in old_ids:
            try:
                pub.delete_message(int(mid))
            except Exception as e:  # noqa: BLE001
                log.info("No se pudo borrar el calendario de evoluciones anterior (%s): %s", mid, e)
        db.set_meta("evocal_photo_id", str(photo_id))
        db.set_meta("evocal_message_ids", json.dumps([photo_id, *text_ids]))
        db.set_meta("evocal_hash", signature)
        db.add_post("evocal", [photo_id, *text_ids])
    return True


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
    summary: dict[str, Any] = {"fetched": 0, "new": 0, "items": 0, "posted": 0}
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
        sections = Sections(db, pub, dry_run)
        with CoverRenderer() as renderer:
            for item in to_post:
                _hydrate(db, item)
                ids = publish_item(pub, renderer, item, cfg, sections)
                if not dry_run:
                    db.mark_item_posted(item.id, ids)
                state = merge(state, item, cfg.timezone)
                summary["posted"] += 1
            update_pinned(db, pub, state, cfg, dry_run)  # guía de General (si no cambia, Telegram lo ignora)
            # El calendario se revisa siempre: también cambia cuando algo caduca o cambia el día
            summary["calendar_updated"] = update_calendar(db, pub, renderer, sections, state, cfg, dry_run)
            summary["evo_calendar_updated"] = update_evo_calendar(db, pub, renderer, sections, state, cfg, dry_run)
        if not dry_run:
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
        # El resumen diario recoge las filtraciones (lo oficial ya está en el calendario)
        items = [i for i in db.items_since((now - timedelta(hours=24)).isoformat(timespec="seconds"))
                 if i.source_type == "leak"]
        if not items:
            return {"daily": "sin novedades"}
        sections = Sections(db, pub, dry_run)
        label = datetime.now(ZoneInfo(cfg.timezone)).strftime("%d/%m/%Y")
        with CoverRenderer() as r:
            cover = r.render(daily_cover_html(items, cfg.channel_title, label), OUT_DIR / "covers" / "daily.png")
        ids = [sections.send("daily", pub.send_photo, cover, f"🗞️ <b>Resumen del día · {label}</b>")]
        for chunk in fmt.split_html(fmt.daily_message(items, label)):
            ids.append(sections.send("daily", pub.send_message, chunk, reply_to=ids[0]))
        if not dry_run:
            db.set_meta("last_daily_at", now.isoformat(timespec="seconds"))
            db.add_post("daily", ids)
        return {"daily": len(items)}
    finally:
        if dry_run:
            pub.write_html("InfoBot FC 27 — resumen diario")
        db.close()


WELCOME = """👋 <b>Bienvenido a InfoBot FC 27</b>

Todas las novedades de EA SPORTS FC 27 Ultimate Team, al momento y en español, ordenadas por secciones:

✅ <b>📅 Calendario</b>: solo lo OFICIAL, con inicio y fin de las próximas 2 semanas
🕵️ <b>Filtraciones</b> por secciones: 🔥 Promos · 🃏 Cartas · 🎯 Objetivos · 🧩 SBC · 🧬 Evoluciones · 📢 Eventos
🗞️ Resumen diario cada noche

Se actualiza solo cada 4 horas. 📌 Arriba tienes fijado el estado actual."""


def setup(cfg: Config, *, dry_run: bool = False, db_path: Path = DB_PATH, state_path: Path = STATE_PATH) -> dict:
    """Prepara el grupo: crea todas las secciones en orden, da la bienvenida, fija el estado y el calendario."""
    db = DB(db_path)
    pub = make_publisher(cfg, dry_run)
    state = expire(load_state(state_path), tz=cfg.timezone)
    try:
        sections = Sections(db, pub, dry_run)
        if not sections.forum:
            raise RuntimeError("El chat no tiene Temas activados: actívalos en los ajustes del grupo")
        created = [k for k in TOPICS if k not in sections.ids]
        for key in TOPICS:
            sections.thread(key)
        if not db.get_meta("welcome_sent"):
            pub.send_message(WELCOME)
            if not dry_run:
                db.set_meta("welcome_sent", "1")
        update_pinned(db, pub, state, cfg, dry_run)
        with CoverRenderer() as renderer:
            update_calendar(db, pub, renderer, sections, state, cfg, dry_run)
        if not dry_run:
            save_state(state_path, state)
        return {"sections_created": created}
    finally:
        if dry_run:
            pub.write_html("InfoBot FC 27 — preparación del grupo")
        db.close()


def reset_group(cfg: Config, *, db_path: Path = DB_PATH, state_path: Path = STATE_PATH) -> dict:
    """Deja el grupo y el bot como nuevos: borra las secciones del bot (con sus mensajes), borra los mensajes de
    General, reinicia la base de datos y el estado, y vuelve a crear las secciones vacías con su introducción."""
    from .telegram import Telegram

    tg = Telegram(cfg.telegram_token, cfg.telegram_channel)
    old = DB(db_path)
    topics = json.loads(old.get_meta("topics") or "{}")
    old.close()

    deleted_topics = 0
    for key, tid in topics.items():
        try:
            tg._call("deleteForumTopic", {"chat_id": tg.chat_id, "message_thread_id": tid})
            deleted_topics += 1
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo borrar la sección %s: %s", key, e)

    # General: se borran todos los mensajes hasta el último (se averigua con un mensaje de prueba)
    probe = tg.send_message("🧹")
    deleted_msgs = 0
    ids = list(range(1, probe + 1))
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        try:
            tg._call("deleteMessages", {"chat_id": tg.chat_id, "message_ids": json.dumps(chunk)})
            deleted_msgs += len(chunk)
        except Exception as e:  # noqa: BLE001 - mensajes de servicio que no se pueden borrar
            log.info("Bloque %s-%s: %s", chunk[0], chunk[-1], e)

    Path(db_path).unlink(missing_ok=True)
    Path(state_path).unlink(missing_ok=True)
    result = setup(cfg, db_path=db_path, state_path=state_path)
    return {"deleted_topics": deleted_topics, "deleted_up_to_message": probe, **result}
