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
    upd = _short_date(state.get("updated_at")) or "—"
    out = [f"📌 <b>ESTADO ACTUAL · {e(title.upper())}</b>", f"<i>Actualizado: {upd}</i>", ""]

    promo = state.get("active_promo")
    out.append("🔥 <b>Promo activa</b>")
    if promo:
        dates = " → ".join(x for x in (_short_date(promo.get("start")), _short_date(promo.get("end"))) if x)
        out.append(f"• {e(promo.get('name'))}{_src(promo)}" + (f" ({dates})" if dates else ""))
    else:
        out.append("• —")

    def section(emoji: str, label: str, entries: list[dict], fmt) -> None:
        out.extend(["", f"{emoji} <b>{label}</b>"])
        out.extend(fmt(x) for x in entries) if entries else out.append("• —")

    section("🎯", "Objetivos en vigor", state.get("objectives", [])[:8], lambda o: (
        f"• {e(o.get('name'))}{_src(o)}"
        + (f" — {e(o.get('reward'))}" if o.get("reward") else "")
        + (f" (hasta {_short_date(o.get('ends'))})" if o.get("ends") else "")
    ))
    section("🧩", "SBCs", state.get("sbcs", [])[:8], lambda s: (
        f"• {e(s.get('name'))}{_src(s)}"
        + (f" — {e(s.get('cost'))}" if s.get("cost") else "")
        + (f" (hasta {_short_date(s.get('ends'))})" if s.get("ends") else "")
    ))
    section("🃏", "Últimas cartas", state.get("recent_cards", [])[:10], lambda c: (
        "• " + " ".join(x for x in (str(c.get("rating") or ""), e(c.get("player")),
                                     f"({e(c.get('position'))})" if c.get("position") else "") if x)
        + (f" — {e(c.get('promo'))}" if c.get("promo") else "") + _src(c)
    ))
    section("🕵️", "Últimas filtraciones", state.get("recent_leaks", [])[:6], lambda l: f"• {e(l.get('title'))}")
    out += ["", "<i>🕵️ = filtración, sin confirmar por EA</i>"]
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
