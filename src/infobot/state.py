"""Estado actual de FC 27 (data/state.json): se fusiona con cada novedad."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import Item

MAX_CARDS = 15
MAX_RECENT = 10
MAX_LIST = 12
MAX_CALENDAR = 40


def empty_state() -> dict[str, Any]:
    return {
        "updated_at": None,
        "active_promo": None,
        "objectives": [],
        "sbcs": [],
        "evolutions": [],
        "events": [],
        "recent_cards": [],
        "recent_updates": [],
        # Solo contenido OFICIAL (disponible en el juego o anunciado por EA): alimenta el calendario
        "calendar": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("recent_leaks", None)  # sustituido por recent_updates
        st = {**empty_state(), **data}
        if "calendar" not in data:  # migración: estados antiguos sin calendario propio
            st["calendar"] = _calendar_from_legacy(st)
        return st
    return empty_state()


def _calendar_from_legacy(st: dict[str, Any]) -> list[dict]:
    out: list[dict] = []
    lists = (("objectives", "objective"), ("sbcs", "sbc"), ("evolutions", "evolution"), ("events", "event"))
    for key, type_ in lists:
        for x in st.get(key, []):
            if x.get("source_type") == "official" and x.get("name"):
                out.append(_cal_entry(type_, x))
    promo = st.get("active_promo")
    if promo and promo.get("source_type") == "official":
        out.append(_cal_entry("promo", promo))
    return out


def _cal_entry(type_: str, x: dict, default_start: str | None = None) -> dict:
    detail = " · ".join(v for v in (x.get("reward"), x.get("cost"), x.get("requirements"), x.get("upgrades")) if v)
    return {
        "type": type_,
        "name": x.get("name", "").strip(),
        "starts": x.get("starts") or x.get("start") or default_start or "",
        "ends": x.get("ends") or x.get("end") or "",
        "detail": detail,
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _upsert(lst: list[dict], entry: dict, key: str, limit: int) -> list[dict]:
    """Inserta al principio; si ya existe (mismo nombre) lo sustituye. Lo oficial no lo pisa nada que no lo sea."""
    name = (entry.get(key) or "").strip().lower()
    out = []
    for old in lst:
        if (old.get(key) or "").strip().lower() == name:
            if old.get("source_type") == "official" and entry.get("source_type") != "official":
                return lst
            continue
        out.append(old)
    return [entry] + out[: limit - 1]


def merge(state: dict[str, Any], item: Item, tz: str = "Europe/Madrid") -> dict[str, Any]:
    st = {**empty_state(), **state}
    src = item.source_type
    ex = item.extra

    promo = ex.get("promo")
    start = _parse_date((promo or {}).get("start"))
    if promo and promo.get("name") and start and start > datetime.now(ZoneInfo(tz)).replace(tzinfo=None):
        # Promo que aún no ha empezado: va al calendario como "próximamente", no como activa
        entry = {"name": f"Promo {promo['name']}", "starts": promo.get("start"), "ends": promo.get("end", ""),
                 "source_type": src}
        st["events"] = _upsert(st["events"], entry, "name", MAX_LIST)
    elif promo and promo.get("name"):
        current = st.get("active_promo") or {}
        same = (current.get("name") or "").lower() == promo["name"].lower()
        if not (same and current.get("source_type") == "official" and src != "official"):
            st["active_promo"] = {**(current if same else {}), **promo, "source_type": src}

    for card in ex.get("cards", []):
        entry = {**card, "source_type": src}
        key_name = f"{card.get('player')}|{card.get('promo', '')}|{card.get('rating', '')}"
        entry["_key"] = key_name
        st["recent_cards"] = _upsert(st["recent_cards"], entry, "_key", MAX_CARDS)

    for obj in ex.get("objectives", []):
        st["objectives"] = _upsert(st["objectives"], {**obj, "source_type": src}, "name", MAX_LIST)
    for sbc in ex.get("sbcs", []):
        st["sbcs"] = _upsert(st["sbcs"], {**sbc, "source_type": src}, "name", MAX_LIST)
    for evo in ex.get("evolutions", []):
        st["evolutions"] = _upsert(st["evolutions"], {**evo, "source_type": src}, "name", MAX_LIST)
    for ev in ex.get("events", []):
        st["events"] = _upsert(st["events"], {**ev, "source_type": src}, "name", MAX_LIST)

    if src == "official":
        st["calendar"] = add_to_calendar(st.get("calendar", []), item, tz)

    now = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    entry = {"title": item.title, "date": now, "source_type": src}
    st["recent_updates"] = _upsert(st.get("recent_updates", []), entry, "title", MAX_RECENT)

    st["updated_at"] = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    return st


def calendar_entries_for(item: Item, tz: str = "Europe/Madrid") -> list[dict]:
    """Entradas de calendario de una novedad oficial (promo, objetivos, SBC, evoluciones, eventos, modos)."""
    # Si EA no da fecha de inicio, se considera activo desde hoy
    today = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")
    ex = item.extra
    out: list[dict] = []
    if ex.get("promo", {}).get("name"):
        out.append(_cal_entry("promo", ex["promo"], today))
    for key, type_ in (("objectives", "objective"), ("sbcs", "sbc"), ("evolutions", "evolution"),
                       ("events", "event"), ("modes", "mode")):
        for x in ex.get(key, []):
            if x.get("name"):
                out.append(_cal_entry(type_, x, today))
    if not out and (item.extra.get("starts") or item.extra.get("ends") or item.kind != "card"):
        out.append(_cal_entry(item.kind, {"name": item.title, "starts": item.extra.get("starts"),
                                          "ends": item.extra.get("ends")}, today))
    return out


def add_to_calendar(cal: list[dict], item: Item, tz: str = "Europe/Madrid") -> list[dict]:
    for entry in calendar_entries_for(item, tz):
        key = (entry["type"], entry["name"].lower())
        old = next((c for c in cal if (c["type"], c["name"].lower()) == key), None)
        if old:  # actualiza sin perder fechas que ya conocíamos
            entry = {k: (entry.get(k) or old.get(k, "")) for k in set(old) | set(entry)}
        cal = [entry] + [c for c in cal if (c["type"], c["name"].lower()) != key]
    return cal[:MAX_CALENDAR]


def expire(state: dict[str, Any], now: datetime | None = None, tz: str = "Europe/Madrid") -> dict[str, Any]:
    """Quita objetivos/SBCs/promo cuya fecha de fin ya ha pasado."""
    now = now or datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    st = {**state}

    def alive(entry: dict) -> bool:
        end = _parse_date(entry.get("ends") or entry.get("end"))
        return end is None or end > now

    for key in ("objectives", "sbcs", "evolutions", "events", "calendar"):
        st[key] = [x for x in st.get(key, []) if alive(x)]
    if st.get("active_promo") and not alive(st["active_promo"]):
        st["active_promo"] = None
    return st
