"""Textos HTML para Telegram: novedad, mensaje fijado y resumen diario."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Any

from ..models import KINDS, SOURCE_TYPES, Item

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024


def e(s: Any) -> str:
    return escape(str(s or ""), quote=False)


def caption(item: Item) -> str:
    m, s = item.meta, item.source_meta
    return f"<b>{m['emoji']} {e(item.title)}</b>\n{s['emoji']} {s['label']} · #{m['tag']}"


def item_message(item: Item, show_source: bool = True) -> str:
    m, s = item.meta, item.source_meta
    parts = [
        f"{m['emoji']} <b>{m['label']} · {e(item.title)}</b>",
        f"{s['emoji']} <b>{s['label']}</b>",
        "",
        e(item.summary),
    ]
    if item.key_facts:
        parts.append("")
        parts += [f"▸ <b>{e(f.get('label'))}</b>: {e(f.get('value'))}" for f in item.key_facts]
    if item.details:
        parts += ["", f"<blockquote expandable>{e(item.details)}</blockquote>"]
    parts += ["", f"#{m['tag']} #{s['tag']} #FC27"]
    if show_source and item.urls:
        # https://x.com/<cuenta>/status/<id> → @cuenta
        links = " · ".join(f'<a href="{e(u)}">@{e(u.split("/")[3])}</a>' for u in item.urls[:3])
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


def _src(entry: dict) -> str:
    return " 🕵️" if entry.get("source_type") == "leak" else ""


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
    """Mensaje fijado en General: guía del grupo + últimas filtraciones."""
    upd = _short_date(state.get("updated_at")) or "—"
    out = [
        f"📌 <b>{e(title.upper())} · CÓMO FUNCIONA</b>",
        "",
        "✅ <b>📅 Calendario</b> → lo OFICIAL: todo lo que ya está en el juego o ha confirmado EA, con su inicio y "
        "su fin en las próximas 2 semanas.",
        "✅ <b>📆 Calendario de evoluciones</b> → todas las evoluciones activas de los próximos 30 días y cuándo "
        "terminan. ⭐ VIP = pase premium.",
        "",
        "🕵️ <b>Filtraciones</b>, cada una en su sección:",
        "🔥 Promos · 🃏 Cartas · 🎯 Objetivos · 🧩 SBC · 🧬 Evoluciones · 📢 Eventos",
        "",
        "🗞️ <b>Resumen diario</b> → cada noche, todas las filtraciones del día.",
    ]
    leaks = state.get("recent_leaks", [])[:6]
    if leaks:
        out += ["", "<b>Últimas filtraciones</b>"] + [f"• {e(l.get('title'))}" for l in leaks]
    out += ["", f"<i>Actualizado: {upd} · Se actualiza solo cada 4 horas</i>"]
    return "\n".join(out)[:TEXT_LIMIT]


def daily_message(items: list[Item], date_label: str) -> str:
    groups: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        groups[it.kind].append(it)
    out = [f"🗞️ <b>RESUMEN DEL DÍA · {e(date_label)}</b>", f"<i>{len(items)} novedades en las últimas 24 h</i>"]
    for kind, meta in KINDS.items():
        if kind not in groups:
            continue
        out += ["", f"{meta['emoji']} <b>{meta['label']}</b>"]
        for it in groups[kind]:
            mark = SOURCE_TYPES[it.source_type]["emoji"] if it.source_type == "leak" else ""
            out.append(f"• {e(it.title)} {mark}".rstrip())
    out += ["", "#ResumenDiario #FC27"]
    return "\n".join(out)
