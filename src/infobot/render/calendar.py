"""Calendario: todo lo activo o por llegar, agrupado por plazo (hoy, mañana, esta semana…)."""

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

TYPE_META = {
    "promo": ("🔥", "Promo"),
    "objective": ("🎯", "Objetivos"),
    "sbc": ("🧩", "SBC"),
    "evolution": ("🧬", "Evolución"),
    "event": ("📢", "Evento"),
}

BUCKETS = [
    ("today", "⏰ Termina hoy"),
    ("tomorrow", "⌛ Termina mañana"),
    ("week", "📆 Esta semana"),
    ("later", "🗓️ Más adelante"),
    ("nodate", "❔ Sin fecha de fin confirmada"),
    ("soon", "🔜 Próximamente"),
]


@dataclass
class Entry:
    type: str
    name: str
    detail: str
    starts: datetime | None
    ends: datetime | None
    leak: bool

    @property
    def emoji(self) -> str:
        return TYPE_META[self.type][0]

    @property
    def type_label(self) -> str:
        return TYPE_META[self.type][1]


def fmt_date(d: datetime | None) -> str:
    if not d:
        return ""
    s = f"{DAYS[d.weekday()]} {d:%d/%m}"
    return s + (f" {d:%H:%M}" if (d.hour, d.minute) != (0, 0) else "")


def _stamp(d: datetime) -> str:
    return f"{DAYS[d.weekday()]} {d:%d/%m %H:%M}"


def entries_from_state(state: dict[str, Any]) -> list[Entry]:
    out: list[Entry] = []

    def add(type_: str, x: dict, detail: str = "") -> None:
        out.append(Entry(
            type=type_, name=x.get("name") or "", detail=detail,
            starts=_parse_date(x.get("starts") or x.get("start")),
            ends=_parse_date(x.get("ends") or x.get("end")),
            leak=x.get("source_type") == "leak",
        ))

    if state.get("active_promo"):
        add("promo", state["active_promo"])
    for o in state.get("objectives", []):
        add("objective", o, o.get("reward", ""))
    for s in state.get("sbcs", []):
        add("sbc", s, " · ".join(x for x in (s.get("reward"), s.get("cost")) if x))
    for e in state.get("evolutions", []):
        add("evolution", e, " · ".join(x for x in (e.get("cost"), e.get("requirements")) if x))
    for e in state.get("events", []):
        add("promo" if (e.get("name") or "").startswith("Promo ") else "event", e)
    return [e for e in out if e.name]


def bucketize(entries: list[Entry], now: datetime) -> dict[str, list[Entry]]:
    today = now.date()
    groups: dict[str, list[Entry]] = {k: [] for k, _ in BUCKETS}
    for e in entries:
        if e.ends and e.ends < now:
            continue
        if e.starts and e.starts > now:
            groups["soon"].append(e)
        elif not e.ends:
            groups["nodate"].append(e)
        elif e.ends.date() == today:
            groups["today"].append(e)
        elif e.ends.date() == today + timedelta(days=1):
            groups["tomorrow"].append(e)
        elif e.ends - now <= timedelta(days=7):
            groups["week"].append(e)
        else:
            groups["later"].append(e)
    far = datetime.max
    for k, lst in groups.items():
        lst.sort(key=lambda e: (e.starts or far) if k == "soon" else (e.ends or far))
    return groups


def _now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz)).replace(tzinfo=None)


def calendar_text(state: dict[str, Any], tz: str = "Europe/Madrid", now: datetime | None = None) -> str:
    now = now or _now(tz)
    groups = bucketize(entries_from_state(state), now)
    out = ["📅 <b>CALENDARIO · FC 27</b>", f"<i>Actualizado: {_stamp(now)}</i>"]
    if not any(groups.values()):
        out += ["", "No hay nada activo ahora mismo. 💤"]
    for key, label in BUCKETS:
        if not groups[key]:
            continue
        out += ["", f"<b>{label}</b>"]
        for e in groups[key]:
            when = f"empieza {fmt_date(e.starts)}" if key == "soon" else (f"hasta {fmt_date(e.ends)}" if e.ends else "")
            line = f"{e.emoji} <b>{escape(e.name)}</b>" + (" 🕵️" if e.leak else "")
            if when:
                line += f" — <i>{when}</i>"
            if e.detail:
                line += f"\n     {escape(e.detail)[:140]}"
            out.append(line)
    out += ["", "<i>🕵️ = filtración, sin confirmar por EA</i>"]
    return "\n".join(out)[:4096]


def calendar_html(state: dict[str, Any], brand: str, tz: str = "Europe/Madrid", now: datetime | None = None) -> tuple[str, int]:
    """Devuelve (html, alto_en_px)."""
    now = now or _now(tz)
    groups = bucketize(entries_from_state(state), now)
    sections = []
    rows = 0
    for key, label in BUCKETS:
        if groups[key]:
            items = [{
                "emoji": e.emoji, "type": e.type_label, "name": e.name, "detail": e.detail[:90], "leak": e.leak,
                "when": (f"Empieza {fmt_date(e.starts)}" if key == "soon" else (fmt_date(e.ends) if e.ends else "—")),
            } for e in groups[key][:10]]
            sections.append({"key": key, "label": label, "rows": items})
            rows += len(items)
    height = max(720, 260 + len(sections) * 70 + rows * 86)
    html = _env.get_template("calendar.html.j2").render(
        fonts=(ASSETS_DIR / "fonts").resolve().as_uri(), brand=brand, sections=sections,
        updated=_stamp(now), height=height,
    )
    return html, height
