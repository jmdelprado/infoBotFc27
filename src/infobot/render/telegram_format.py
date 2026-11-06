"""Textos HTML para Telegram: novedad, mensaje fijado y resumen diario."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Any

from ..models import KINDS, Item

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024


def e(s: Any) -> str:
    return escape(str(s or ""), quote=False)


def label_line(item: Item) -> str:
    """"✅ OFICIAL" / "🔮 PREDICCIÓN"; vacío si va sin etiqueta."""
    s = item.source_meta
    return f"{s['emoji']} {s['label']}" if s["label"] else ""


def caption(item: Item) -> str:
    m = item.meta
    second = " · ".join(x for x in (label_line(item), f"#{m['tag']}") if x)
    return f"<b>{m['emoji']} {e(item.title)}</b>\n{second}"


def _card_line(card: dict) -> str:
    rating = card.get("rating")
    main = " ".join(str(x) for x in (card.get("player"), rating, card.get("position")) if x)
    extra = " · ".join(str(card[k]) for k in ("club", "nation") if card.get(k))
    line = f"• <b>{e(main)}</b>" + (f" ({e(extra)})" if extra else "")
    return line + (" 🔮" if card.get("predicted") else "")


def cards_block(cards: list[dict]) -> list[str]:
    """Cartas ordenadas por media, de mayor a menor."""
    if not cards:
        return []
    ordered = sorted(cards, key=lambda c: -(c.get("rating") or 0))
    out = ["", "🃏 <b>Cartas</b>"] + [_card_line(c) for c in ordered]
    if any(c.get("predicted") for c in cards) and not all(c.get("predicted") for c in cards):
        out.append("<i>🔮 = predicción</i>")
    return out


def story_message(item: Item, show_source: bool = True) -> str:
    """Ficha completa: título, etiqueta, resumen, datos clave, cartas, detalle desplegable y fuentes."""
    m = item.meta
    parts = [f"{m['emoji']} <b>{e(item.title.upper())}</b>"]
    if label_line(item):
        parts.append(f"<b>{label_line(item)}</b>")
    parts += ["", e(item.summary)]
    if item.key_facts:
        parts.append("")
        parts += [f"▸ <b>{e(f.get('label'))}</b>: {e(f.get('value'))}" for f in item.key_facts]
    parts += cards_block(item.extra.get("cards") or [])
    if item.details:
        parts += ["", f"<blockquote expandable>{e(item.details)}</blockquote>"]
    parts += ["", f"#{m['tag']} #FC27"]
    if show_source and item.urls:
        # https://x.com/<cuenta>/status/<id> → @cuenta (las 3 más recientes)
        links = " · ".join(f'<a href="{e(u)}">@{e(u.split("/")[3])}</a>' for u in item.urls[-3:])
        parts.append(f"<i>Fuente: {links}</i>")
    return "\n".join(parts)


def split_html(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """Divide un texto largo por líneas, sin romper etiquetas abiertas de una línea a otra
    (cada bloque <blockquote> se cierra y se reabre si hace falta)."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    cur = ""
    open_quote = False
    for line in text.split("\n"):
        candidate = (cur + "\n" + line) if cur else line
        closing = "</blockquote>" if open_quote and "</blockquote>" not in line else ""
        if len(candidate) + len(closing) > limit and cur:
            chunks.append(cur + ("</blockquote>" if open_quote else ""))
            cur = ("<blockquote expandable>" if open_quote else "") + line
        else:
            cur = candidate
        # Líneas más largas que el límite: se cortan a lo bruto
        while len(cur) > limit:
            chunks.append(cur[: limit - 20] + ("</blockquote>" if open_quote else ""))
            cur = ("<blockquote expandable>" if open_quote else "") + cur[limit - 20 :]
        if "<blockquote" in line and "</blockquote>" not in line:
            open_quote = True
        if "</blockquote>" in line:
            open_quote = False
    if cur:
        chunks.append(cur)
    return chunks


def _short_date(value: str | None) -> str:
    if not value:
        return ""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(value, fmt)
            return d.strftime("%d/%m %H:%M") if "%H" in fmt else d.strftime("%d/%m")
        except ValueError:
            continue
    return value


def pinned_message(state: dict[str, Any], title: str = "InfoBot FC 27") -> str:
    """Mensaje fijado en General: guía del grupo + últimas novedades."""
    upd = _short_date(state.get("updated_at")) or "—"
    out = [
        f"📌 <b>{e(title.upper())} · CÓMO FUNCIONA</b>",
        "",
        "✅ <b>📅 Calendario</b> → lo OFICIAL: todo lo que ya está en el juego o ha confirmado EA, con su inicio y "
        "su fin en las próximas 2 semanas.",
        "✅ <b>📆 Calendario de evoluciones</b> → todas las evoluciones activas de los próximos 30 días y cuándo "
        "terminan. ⭐ VIP = pase premium.",
        "",
        "🗂️ <b>Un tema = un mensaje</b>, cada uno en su sección:",
        "🔥 Promos · 🃏 Cartas · 🎯 Objetivos · 🧩 SBC · 🧬 Evoluciones · 📢 Eventos",
        "Cuando hay novedades, el mensaje del tema se vuelve a publicar completo abajo (y se borra el anterior).",
        "",
        "✅ <b>OFICIAL</b> → ya está en el juego, lo ha anunciado EA o son los datos definitivos.",
        "🔮 <b>PREDICCIÓN</b> → medias, PS o mejoras estimadas.",
        "Sin etiqueta → información de fuentes fiables: se da por hecho.",
        "",
        "🗞️ <b>Resumen diario</b> → cada noche, todo lo que ha cambiado en el día.",
    ]
    recent = state.get("recent_updates", [])[:6]
    if recent:
        out += ["", "<b>Últimas novedades</b>"] + [
            f"• {e(r.get('title'))}" + (" ✅" if r.get("source_type") == "official" else
                                       " 🔮" if r.get("source_type") == "prediction" else "")
            for r in recent]
    out += ["", f"<i>Actualizado: {upd} · Se actualiza solo cada 4 horas</i>"]
    return "\n".join(out)[:TEXT_LIMIT]


def daily_message(stories: list[Item], date_label: str) -> str:
    """Resumen del día: las fichas creadas o actualizadas en las últimas 24 h, por sección."""
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in stories:
        groups[it.kind].append(it)
    n = len(stories)
    out = [f"🗞️ <b>LO QUE HA CAMBIADO HOY · {e(date_label)}</b>",
           f"<i>{n} {'tema actualizado' if n == 1 else 'temas actualizados'} en las últimas 24 h</i>"]
    for kind, meta in KINDS.items():
        if kind not in groups:
            continue
        out += ["", f"{meta['emoji']} <b>{meta['label']}</b>"]
        for it in groups[kind]:
            mark = it.source_meta["emoji"]
            line = f"• <b>{e(it.title)}</b> {mark}".rstrip()
            out.append(f"{line}\n   {e(it.summary)}" if it.summary else line)
    out += ["", "#ResumenDiario #FC27"]
    return "\n".join(out)
