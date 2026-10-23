"""Calendario OFICIAL: imagen de las próximas dos semanas (estilo diagrama de Gantt) + lista en texto.

Solo usa state["calendar"], donde únicamente entra contenido oficial (ya disponible en el juego o anunciado por EA).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from ..config import ASSETS_DIR
from ..state import _parse_date
from .cover import _env

DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
WINDOW_DAYS = 14

TYPE_META = {
    "promo": ("🔥", "Promo", "#ff7a18"),
    "objective": ("🎯", "Objetivos", "#2bd67b"),
    "sbc": ("🧩", "SBC", "#36a2ff"),
    "evolution": ("🧬", "Evolución", "#b26bff"),
    "mode": ("🎮", "Modo de juego", "#ff3d7f"),
    "event": ("📢", "Evento", "#f7c948"),
    "card": ("🃏", "Carta", "#f7d774"),
}


@dataclass
class Entry:
    type: str
    name: str
    detail: str
    starts: datetime | None
    ends: datetime | None

    @property
    def meta(self) -> tuple[str, str, str]:
        return TYPE_META.get(self.type, TYPE_META["event"])


def fmt_date(d: datetime | None) -> str:
    if not d:
        return ""
    s = f"{DAYS[d.weekday()]} {d:%d/%m}"
    return s + (f" {d:%H:%M}" if (d.hour, d.minute) != (0, 0) else "")


def _stamp(d: datetime) -> str:
    return f"{DAYS[d.weekday()]} {d:%d/%m %H:%M}"


def _now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz)).replace(tzinfo=None)


def entries_from_state(state: dict[str, Any]) -> list[Entry]:
    out = []
    for c in state.get("calendar", []):
        if not c.get("name"):
            continue
        out.append(Entry(
            type=c.get("type", "event"), name=c["name"], detail=c.get("detail", ""),
            starts=_parse_date(c.get("starts")), ends=_parse_date(c.get("ends")),
        ))
    return out


def split(entries: list[Entry], now: datetime) -> tuple[list[Entry], list[Entry], list[Entry]]:
    """(en vigor, empiezan en las próximas 2 semanas, empiezan más tarde). Lo caducado se descarta."""
    window_end = now + timedelta(days=WINDOW_DAYS)
    active, soon, later = [], [], []
    for e in entries:
        if e.ends and e.ends < now:
            continue
        if e.starts and e.starts > now:
            (soon if e.starts < window_end else later).append(e)
        else:
            active.append(e)
    far = datetime.max
    active.sort(key=lambda e: (e.ends or far, e.name))
    soon.sort(key=lambda e: (e.starts or far, e.name))
    later.sort(key=lambda e: (e.starts or far, e.name))
    return active, soon, later


def calendar_text(state: dict[str, Any], tz: str = "Europe/Madrid", now: datetime | None = None) -> str:
    now = now or _now(tz)
    active, soon, later = split(entries_from_state(state), now)
    out = ["📅 <b>CALENDARIO OFICIAL · FC 27</b>", f"<i>Actualizado: {_stamp(now)}</i>"]
    if not (active or soon or later):
        out += ["", "No hay nada oficial activo ahora mismo. 💤"]

    def line(e: Entry, when: str) -> str:
        emoji, label, _ = e.meta
        s = f"{emoji} <b>{escape(e.name)}</b> <i>({label})</i>"
        if when:
            s += f" — {when}"
        if e.detail:
            s += f"\n     {escape(e.detail)[:140]}"
        return s

    if active:
        out += ["", "<b>✅ En vigor</b>"]
        out += [line(e, f"hasta {fmt_date(e.ends)}" if e.ends else "sin fecha de fin") for e in active]
    if soon:
        out += ["", "<b>🔜 Próximos 14 días</b>"]
        out += [line(e, f"del {fmt_date(e.starts)}" + (f" al {fmt_date(e.ends)}" if e.ends else "")) for e in soon]
    if later:
        out += ["", "<b>🗓️ Más adelante</b>"]
        out += [line(e, f"desde {fmt_date(e.starts)}") for e in later]
    return "\n".join(out)[:4096]


def calendar_html(state: dict[str, Any], brand: str, tz: str = "Europe/Madrid",
                  now: datetime | None = None) -> tuple[str, int]:
    """Diagrama de las próximas dos semanas. Devuelve (html, alto_en_px)."""
    now = now or _now(tz)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = day0 + timedelta(days=WINDOW_DAYS)
    total = (window_end - day0).total_seconds()
    active, soon, later = split(entries_from_state(state), now)

    days = []
    for i in range(WINDOW_DAYS):
        d = day0 + timedelta(days=i)
        days.append({"dow": DAYS[d.weekday()], "num": d.day, "weekend": d.weekday() >= 5, "today": i == 0})

    rows = []
    for e in active + soon:
        emoji, label, color = e.meta
        start = max(e.starts or day0, day0)
        end = min(e.ends or window_end, window_end)
        left = max(0.0, (start - day0).total_seconds() / total * 100)
        width = max(2.5, (end - start).total_seconds() / total * 100)
        if e.ends:
            when = f"hasta {fmt_date(e.ends)}" if not (e.starts and e.starts > now) else \
                f"{fmt_date(e.starts)} → {fmt_date(e.ends)}"
        else:
            when = "sin fecha de fin" if not (e.starts and e.starts > now) else f"desde {fmt_date(e.starts)}"
        rows.append({
            "emoji": emoji, "label": label, "color": color, "name": e.name, "detail": e.detail[:70],
            "left": round(left, 2), "width": round(min(width, 100 - left), 2), "when": when,
            "open_end": e.ends is None or e.ends > window_end, "upcoming": bool(e.starts and e.starts > now),
            "no_end": e.ends is None, "short": width < 22,
        })
    later_rows = [{"emoji": e.meta[0], "name": e.name, "when": fmt_date(e.starts)} for e in later[:6]]
    now_pct = round((now - day0).total_seconds() / total * 100, 2)
    height = 300 + max(len(rows), 1) * 78 + (90 + len(later_rows) * 40 if later_rows else 0)
    html = _env.get_template("calendar.html.j2").render(
        fonts=(ASSETS_DIR / "fonts").resolve().as_uri(), brand=brand, days=days, rows=rows,
        later=later_rows, now_pct=now_pct, updated=_stamp(now), height=height,
        range_label=f"{day0:%d/%m} – {(window_end - timedelta(days=1)):%d/%m}",
    )
    return html, height
