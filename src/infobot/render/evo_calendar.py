"""Calendario de evoluciones: los próximos 30 días con el plazo de cada evolución activa (datos de FUT.GG)."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from ..config import ASSETS_DIR
from ..state import _parse_date
from .calendar import DAYS, _stamp, fmt_date
from .cover import _env

WINDOW_DAYS = 30
COLOR_STANDARD = "#b26bff"
COLOR_PREMIUM = "#f5b82e"
COLOR_SEASON = "#36a2ff"


def _now(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz)).replace(tzinfo=None)


def _kind(e: dict) -> tuple[str, str]:
    if e.get("premium"):
        return "Pase premium", COLOR_PREMIUM
    if e.get("season_pass"):
        return "Pase de temporada", COLOR_SEASON
    return "Evolución", COLOR_STANDARD


def _detail(e: dict, n_upgrades: int = 2) -> str:
    parts = [e.get("requirements") or "", e.get("cost") or ""]
    if e.get("upgrades"):
        parts.append(", ".join(e["upgrades"][:n_upgrades]))
    return " · ".join(p for p in parts if p)


def evo_calendar_html(evos: list[dict], brand: str, tz: str = "Europe/Madrid",
                      now: datetime | None = None) -> tuple[str, int]:
    now = now or _now(tz)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = day0 + timedelta(days=WINDOW_DAYS)
    total = (window_end - day0).total_seconds()

    days = [{"dow": DAYS[(day0 + timedelta(days=i)).weekday()][:2], "num": (day0 + timedelta(days=i)).day,
             "weekend": (day0 + timedelta(days=i)).weekday() >= 5, "today": i == 0} for i in range(WINDOW_DAYS)]
    rows = []
    for e in evos:
        start, end = _parse_date(e.get("starts")) or day0, _parse_date(e.get("ends"))
        if not end or end < now:
            continue
        label, color = _kind(e)
        s, t = max(start, day0), min(end, window_end)
        left = max(0.0, (s - day0).total_seconds() / total * 100)
        width = max(1.5, (t - s).total_seconds() / total * 100)
        rows.append({
            "emoji": "⭐" if e.get("premium") else "🧬", "label": label, "color": color, "name": e["name"],
            "vip": bool(e.get("premium")), "detail": _detail(e)[:80],
            "left": round(left, 2), "width": round(min(width, 100 - left), 2),
            "when": f"termina {fmt_date(end)}", "open_end": end > window_end, "upcoming": start > now,
            "no_end": False, "short": width < 16,
        })
    now_pct = round((now - day0).total_seconds() / total * 100, 2)
    height = 300 + max(len(rows), 1) * 78
    html = _env.get_template("calendar.html.j2").render(
        fonts=(ASSETS_DIR / "fonts").resolve().as_uri(), brand=brand, days=days, rows=rows, later=[],
        now_pct=now_pct, updated=_stamp(now), height=height, width=1900, label_width=500,
        title="🧬 Evoluciones", badge="⭐ VIP = pase premium · próximos 30 días",
        range_label=f"{day0:%d/%m} – {(window_end - timedelta(days=1)):%d/%m}", source="Datos: FUT.GG",
    )
    return html, height


def evo_calendar_text(evos: list[dict], tz: str = "Europe/Madrid", now: datetime | None = None) -> str:
    """Lista por plazos: terminan en 48 h / esta semana / más adelante."""
    now = now or _now(tz)
    groups: dict[str, list[dict]] = {"soon": [], "week": [], "later": []}
    for e in evos:
        end = _parse_date(e.get("ends"))
        if not end or end < now:
            continue
        key = "soon" if end - now <= timedelta(hours=48) else ("week" if end - now <= timedelta(days=7) else "later")
        groups[key].append(e)
    labels = {"soon": "⏰ <b>Terminan en menos de 48 h</b>", "week": "📆 <b>Terminan esta semana</b>",
              "later": "🗓️ <b>Más adelante</b>"}
    out = ["🧬 <b>CALENDARIO DE EVOLUCIONES · FC 27</b>", f"<i>Actualizado: {_stamp(now)} · ⭐ VIP = pase premium</i>"]
    if not any(groups.values()):
        out += ["", "No hay evoluciones activas ahora mismo. 💤"]
    for key in ("soon", "week", "later"):
        if not groups[key]:
            continue
        out += ["", labels[key]]
        for e in groups[key]:
            vip = " ⭐ <b>VIP</b>" if e.get("premium") else ""
            sp = f" (nivel {e['sp_level']} del pase)" if e.get("sp_level") else ""
            out.append(f"• <b>{escape(e['name'])}</b>{vip}{sp} — termina {fmt_date(_parse_date(e['ends']))}")
            det = _detail(e, 3)
            if det:
                out.append(f"   <i>{escape(det)}</i>")
    out += ["", "<i>Datos de FUT.GG · Horas de España</i>"]
    return "\n".join(out)


def evo_signature(evos: list[dict], tz: str = "Europe/Madrid") -> str:
    import hashlib
    import json

    today = _now(tz).strftime("%Y-%m-%d")
    key = [(e.get("id"), e.get("ends"), e.get("premium")) for e in evos]
    return hashlib.sha1((today + json.dumps(key)).encode()).hexdigest()


__all__: list[Any] = ["evo_calendar_html", "evo_calendar_text", "evo_signature"]
