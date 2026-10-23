"""Estado actual de FC 27 (data/state.json): se fusiona con cada novedad."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import Item

MAX_CARDS = 15
MAX_LEAKS = 10
MAX_LIST = 12


def empty_state() -> dict[str, Any]:
    return {
        "updated_at": None,
        "active_promo": None,
        "objectives": [],
        "sbcs": [],
        "recent_cards": [],
        "recent_leaks": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**empty_state(), **data}
    return empty_state()


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
    """Inserta al principio; si ya existe (mismo nombre) lo sustituye. Lo oficial no lo pisa una filtración."""
    name = (entry.get(key) or "").strip().lower()
    out = []
    for old in lst:
        if (old.get(key) or "").strip().lower() == name:
            if old.get("source_type") == "official" and entry.get("source_type") == "leak":
                return lst
            continue
        out.append(old)
    return [entry] + out[: limit - 1]


def merge(state: dict[str, Any], item: Item, tz: str = "Europe/Madrid") -> dict[str, Any]:
    st = {**empty_state(), **state}
    src = item.source_type
    ex = item.extra

    promo = ex.get("promo")
    if promo and promo.get("name"):
        current = st.get("active_promo") or {}
        same = (current.get("name") or "").lower() == promo["name"].lower()
        if not (same and current.get("source_type") == "official" and src == "leak"):
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

    if src == "leak":
        now = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
        st["recent_leaks"] = _upsert(st["recent_leaks"], {"title": item.title, "date": now}, "title", MAX_LEAKS)

    st["updated_at"] = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    return st


def expire(state: dict[str, Any], now: datetime | None = None, tz: str = "Europe/Madrid") -> dict[str, Any]:
    """Quita objetivos/SBCs/promo cuya fecha de fin ya ha pasado."""
    now = now or datetime.now(ZoneInfo(tz)).replace(tzinfo=None)
    st = {**state}

    def alive(entry: dict) -> bool:
        end = _parse_date(entry.get("ends") or entry.get("end"))
        return end is None or end > now

    st["objectives"] = [o for o in st.get("objectives", []) if alive(o)]
    st["sbcs"] = [s for s in st.get("sbcs", []) if alive(s)]
    if st.get("active_promo") and not alive(st["active_promo"]):
        st["active_promo"] = None
    return st
