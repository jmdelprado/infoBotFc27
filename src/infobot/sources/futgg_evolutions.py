"""Evoluciones activas desde FUT.GG (datos oficiales del juego, con fechas exactas).

La página https://www.fut.gg/evolutions/ incrusta los datos como scripts de JavaScript; se ejecutan con Node
(js/futgg_extract.js) para obtener un JSON limpio.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger(__name__)

URL = "https://www.fut.gg/evolutions/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
EXTRACTOR = Path(__file__).with_name("js") / "futgg_extract.js"
# Las que duran más que esto son permanentes (las de PlayStyle+ de la tienda, que duran toda la temporada)
MAX_DURATION = timedelta(days=90)

LABELS_ES = {
    "Overall": "Media", "PlayStyle": "PlayStyle", "PlayStyle+": "PlayStyle+", "WF": "Pierna mala",
    "SM": "Filigranas", "Rarity": "Rareza", "Sprint Speed": "Velocidad", "Acceleration": "Aceleración",
    "Finishing": "Definición", "Stamina": "Resistencia", "Strength": "Fuerza", "Long Passing": "Pase largo",
    "Short Passing": "Pase corto", "Dribbling (attr.)": "Regate", "Long Shots": "Tiros lejanos",
}


# Códigos de posición de EA → abreviatura en español
POSITIONS_ES = {
    0: "POR", 1: "LIB", 2: "CAD", 3: "LD", 4: "DFC", 5: "DFC", 6: "DFC", 7: "LI", 8: "CAI", 9: "MCD", 10: "MCD",
    11: "MCD", 12: "MD", 13: "MC", 14: "MC", 15: "MC", 16: "MI", 17: "MCO", 18: "MCO", 19: "MCO", 20: "SD",
    21: "SD", 22: "SD", 23: "ED", 24: "DC", 25: "DC", 26: "DC", 27: "EI",
}
LABELS_ES.update({"Passing": "Pase", "Defending": "Defensa", "Reactions": "Reacciones", "Shooting": "Tiro",
                  "Pace": "Ritmo", "Physical": "Físico", "Dribbling": "Regate", "Role++": "Rol++", "Role+": "Rol+"})


class EvolutionsError(RuntimeError):
    pass


def fetch_html(client: httpx.Client | None = None) -> str:
    own = client is None
    client = client or httpx.Client(timeout=40, headers={"User-Agent": UA}, follow_redirects=True)
    try:
        r = client.get(URL)
        if r.status_code != 200:
            raise EvolutionsError(f"FUT.GG respondió HTTP {r.status_code}")
        return r.text
    finally:
        if own:
            client.close()


def extract(html: str) -> list[dict]:
    node = shutil.which("node")
    if not node:
        raise EvolutionsError("No se encuentra Node.js para leer los datos de FUT.GG")
    proc = subprocess.run([node, str(EXTRACTOR)], input=html, capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    if proc.returncode != 0:
        raise EvolutionsError(f"Error leyendo FUT.GG: {proc.stderr[-400:]}")
    data = json.loads(proc.stdout or "[]")
    if not data:
        raise EvolutionsError("FUT.GG no devolvió evoluciones (¿ha cambiado la web?)")
    return data


def _dt(value: str | None, tz: str) -> datetime | None:
    if not value:
        return None
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return d.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def is_premium(e: dict) -> bool:
    return "SP+" in (e.get("name") or "") or "premium season pass" in (e.get("description") or "").lower()


def is_season_pass(e: dict) -> bool:
    return bool(re.search(r"\[SP\+? ?\d*\]", e.get("name") or "")) or "season pass" in (e.get("description") or "").lower()


def _upgrade_text(u: dict) -> str:
    label = LABELS_ES.get(u.get("label", ""), u.get("label", ""))
    value = (u.get("value") or "").replace("★", "⭐")
    return f"{label} {value}".strip()


def normalize(raw: list[dict], tz: str = "Europe/Madrid", now: datetime | None = None) -> list[dict]:
    """Filtra lo que interesa (sin cosméticas, tutoriales ni permanentes) y lo deja listo para el calendario."""
    now = now or datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).replace(tzinfo=None)
    out = []
    for e in raw:
        name = (e.get("name") or "").strip()
        ups = e.get("upgrades") or []
        if not name or name.lower().startswith("intro to"):
            continue
        if ups and all(u.get("label") == "Cosmetic" for u in ups):
            continue
        start, end = _dt(e.get("createdAt"), tz), _dt(e.get("endTime"), tz)
        if not end or end < now:
            continue
        if start and end - start > MAX_DURATION:
            continue
        req = []
        if e.get("maxOverall"):
            req.append(f"Media ≤{e['maxOverall']}")
        if e.get("minOverall"):
            req.append(f"Media ≥{e['minOverall']}")
        if e.get("positions"):
            pos = list(dict.fromkeys(POSITIONS_ES.get(int(x), str(x)) for x in e["positions"]))
            req.append("/".join(pos))
        cost = []
        if e.get("coinsCost"):
            cost.append(f"{e['coinsCost']:,}".replace(",", ".") + " monedas")
        if e.get("pointsCost"):
            cost.append(f"{e['pointsCost']} FC Points")
        clean_name = re.sub(r"\s*\[SP\+? ?\d*\]\s*", "", name).strip()
        sp_level = re.search(r"\[SP\+? ?(\d+)\]", name)
        out.append({
            "id": e.get("id"),
            "name": clean_name,
            "premium": is_premium(e),
            "season_pass": is_season_pass(e),
            "sp_level": int(sp_level.group(1)) if sp_level else None,
            "starts": start.strftime("%Y-%m-%d %H:%M") if start else "",
            "ends": end.strftime("%Y-%m-%d %H:%M"),
            "free": not cost,
            "cost": " + ".join(cost) if cost else "Gratis",
            "requirements": " · ".join(req),
            "upgrades": [_upgrade_text(u) for u in ups if u.get("label") != "Cosmetic"][:4],
            "url": "https://www.fut.gg" + (e.get("url") or ""),
        })
    out.sort(key=lambda x: (x["ends"], x["name"]))
    return out


def fetch_evolutions(tz: str = "Europe/Madrid") -> list[dict]:
    evos = normalize(extract(fetch_html()), tz)
    log.info("FUT.GG: %d evoluciones activas", len(evos))
    return evos
