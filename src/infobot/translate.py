"""Traducción al español de nombres del juego (evoluciones, PlayStyles, mejoras) con Claude Code.

Las traducciones se guardan en data/translations.json para no pedir dos veces la misma.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import DATA_DIR

log = logging.getLogger(__name__)
CACHE = DATA_DIR / "translations.json"

SYSTEM = """Eres traductor oficial de EA SPORTS FC 27 al español de España.
Te doy textos en inglés del modo Ultimate Team (nombres de evoluciones, PlayStyles, mejoras de cartas).
Devuélvelos tal y como aparecen en la VERSIÓN ESPAÑOLA DEL JUEGO.
- Usa los nombres oficiales de EA en español cuando los conozcas (PlayStyles, posiciones, atributos).
- Los nombres de promos y eventos que EA deja en inglés (Ultimate Scream, Future Stars, Ones to Watch, TOTW…)
  se dejan en inglés.
- Si no conoces el nombre oficial, haz una traducción natural y corta, sin explicaciones.
- Conserva números, signos (+, ★, ⭐) y mayúsculas iniciales."""


def _load() -> dict[str, str]:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(cache: dict[str, str]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def translate(texts: list[str], model: str = "sonnet") -> dict[str, str]:
    """Devuelve {texto: traducción}. Si Claude falla, devuelve el texto original."""
    from .analyzer import _claude_bin  # reutiliza la búsqueda del ejecutable

    cache = _load()
    pending = sorted({t for t in texts if t and t not in cache})
    if pending:
        schema = {
            "type": "object", "additionalProperties": False, "required": ["translations"],
            "properties": {"translations": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["en", "es"],
                "properties": {"en": {"type": "string"}, "es": {"type": "string"}}}}},
        }
        import subprocess

        prompt = "Traduce estos textos:\n" + "\n".join(f"- {t}" for t in pending)
        cmd = [_claude_bin(), "-p", "--output-format", "json", "--json-schema", json.dumps(schema),
               "--model", model, "--tools", "", "--system-prompt", SYSTEM, "--strict-mcp-config",
               "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence"]
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=300)
            from .analyzer import parse_claude_output

            data = parse_claude_output(proc.stdout)
            for pair in data.get("translations", []):
                if pair.get("en") in pending and pair.get("es"):
                    cache[pair["en"]] = pair["es"].strip()
            _save(cache)
            log.info("Traducidos %d textos nuevos", len(pending))
        except Exception as e:  # noqa: BLE001 - sin traducción se muestra el original
            log.warning("No se pudo traducir: %s", e)
    return {t: cache.get(t, t) for t in texts}


def translate_evolutions(evos: list[dict], model: str = "sonnet") -> list[dict]:
    texts = [e["name"] for e in evos] + [u for e in evos for u in e.get("upgrades", [])]
    tr = translate(texts, model)
    return [{**e, "name": tr.get(e["name"], e["name"]),
             "upgrades": [tr.get(u, u) for u in e.get("upgrades", [])]} for e in evos]
