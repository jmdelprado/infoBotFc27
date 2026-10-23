"""Análisis de tweets con Claude Code en modo no interactivo (`claude -p`).

Usa la suscripción del propietario (CLAUDE_CODE_OAUTH_TOKEN en CI, o la sesión local), sin API de pago.
Claude lee las imágenes con la herramienta Read y devuelve JSON validado por --json-schema.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import MEDIA_DIR, Config
from .models import KINDS, Item, Tweet

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("analysis.schema.json")

SYSTEM = """Eres el editor de "InfoBot FC 27", un canal de Telegram en español sobre EA SPORTS FC 27 Ultimate Team.
Recibes tweets de cuentas de información y filtraciones. Tu trabajo es convertirlos en novedades claras y completas.

REGLAS
1. Solo interesan novedades de FC 27 Ultimate Team. Tipos (kind):
   - "promo": promos/equipos (Ultimate Scream, TOTW, Thunderstruck…).
   - "card": cartas concretas (jugador, media, posición).
   - "objective": objetivos (tareas con recompensa).
   - "sbc": desafíos de creación de plantillas.
   - "evolution": evoluciones (requisitos para meter la carta, coste, niveles y mejoras).
   - "mode": MODOS DE JUEGO para jugar: torneos (p. ej. Torneo Eliminatorio Diario), Rivals/Champions con recompensas
     especiales, Squad Battles especiales, Circuito Legado, drafts, eventos en directo jugables.
   - DESCARTA SIEMPRE todo lo relacionado con "The Grounds" (objetivos, modo, recompensas…): va a ignored_tweet_ids.
   - "event": el resto (mantenimientos, tienda/tokens, galería, packs, notas de parche relevantes para UT…).
   Lo demás (opiniones, encuestas, sorteos, bromas, quejas, autopromoción, otros juegos) va a ignored_tweet_ids.
2. NUNCA inventes datos. Si un dato no está en el texto ni en la imagen, no lo pongas. Copia las cifras tal cual.
3. MIRA TODAS LAS IMÁGENES con la herramienta Read: muchas veces la información (media, posición, requisitos,
   recompensas, fechas) solo está en la imagen. Transcribe lo que veas.
4. source_type — sé ESTRICTO, es lo más importante:
   - "official" SOLO si el contenido YA ESTÁ DISPONIBLE en el juego ahora mismo o EA lo ha ANUNCIADO oficialmente
     con fecha: "ya disponible", "live", "out now", "ya podéis", "available now", un SBC/objetivo/evolución/torneo
     activo que se describe como jugable hoy, un mantenimiento anunciado por EA, stats oficiales publicadas por EA
     de cartas que ya están en sobres. Lo oficial va al CALENDARIO, así que necesita fechas.
   - "leak" para TODO lo demás: lo que aún no ha salido, "expected", "leaked", "coming", "soon", "rumour",
     "llegaría", "mañana saldrá", "next week", diseños, equipos o cartas antes de su lanzamiento, predicciones,
     datamining, "según fuentes", capturas filtradas. Ante la mínima duda → "leak".
5. Agrupa en UNA sola novedad los tweets que hablen de lo mismo (p. ej. varios tweets de la misma promo).
6. Si una novedad ya aparece en "YA PUBLICADO" y el tweet no aporta nada nuevo, ignóralo.
   Si aporta algo nuevo (p. ej. que una filtración ya está disponible), crea la novedad como "official".
7. Todo en español de España, claro y natural. Los nombres propios (jugadores, promos, clubes) no se traducen.
8. Campos:
   - title: corto y llamativo (máx. 70 caracteres), sin emoji.
   - summary: 1-2 frases con lo esencial.
   - details: explicación completa, autosuficiente; el lector NO va a abrir el tweet. Usa líneas que empiecen por "• ".
   - key_facts: 2-6 pares etiqueta/valor (p. ej. "Media": "91", "Termina": "30/10 19:00").
   - images: nombres de archivo de las imágenes útiles para la novedad (exactamente como se te dan).
   - starts / ends: inicio y fin de la novedad si se conocen.
   - promo/cards/objectives/sbcs/evolutions/modes/events: rellénalos cuando aplique; los oficiales alimentan el
     CALENDARIO. Pon fechas de inicio (start/starts) y fin (end/ends) SIEMPRE que se puedan deducir, en hora de
     España y en formato estricto "YYYY-MM-DD HH:MM" (o "YYYY-MM-DD"). Resuelve fechas relativas ("hasta el lunes",
     "next Friday 6PM UK", "ends in 3 days") usando la fecha actual y la fecha del tweet. Si no se pueden deducir,
     deja el campo vacío.
   - evolutions: requirements = requisitos para meter la carta; upgrades = mejoras que da; cost = coste.
9. Cada tweet_id de la entrada debe aparecer exactamente una vez: o en una novedad, o en ignored_tweet_ids.
"""


def _build_prompt(tweets: list[Tweet], state: dict[str, Any], recent_titles: list[str], tz: str) -> str:
    now = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    lines = [f"Fecha y hora actual (España): {now}", ""]
    lines.append("ESTADO ACTUAL DEL CANAL (contexto):")
    lines.append(json.dumps(state, ensure_ascii=False)[:4000])
    lines.append("")
    lines.append("YA PUBLICADO (últimos días):")
    lines += [f"- {t}" for t in recent_titles[-40:]] or ["- (nada)"]
    lines.append("")
    lines.append("TWEETS NUEVOS:")
    for t in tweets:
        lines.append("-----")
        lines.append(f"tweet_id: {t.id}")
        lines.append(f"cuenta: @{t.account}")
        lines.append(f"fecha: {t.created_at.isoformat()}")
        lines.append("texto:")
        lines.append(t.text)
        if t.local_media:
            lines.append("imágenes (léelas con Read):")
            for name in t.local_media:
                lines.append(f"  - {name}  →  {MEDIA_DIR / name}")
    lines.append("-----")
    lines.append("Devuelve el JSON con items e ignored_tweet_ids.")
    return "\n".join(lines)


def _claude_bin() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("No se encuentra el ejecutable `claude` (Claude Code CLI)")
    return exe


def call_claude(prompt: str, model: str, schema: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        _claude_bin(), "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema, separators=(",", ":")),
        "--model", model,
        "--tools", "Read",
        "--allowedTools", "Read",
        "--add-dir", str(MEDIA_DIR),
        # Sustituye el prompt por defecto y no carga ajustes/MCP/skills del usuario:
        # baja el consumo de ~90k a ~1k tokens de contexto por llamada.
        "--system-prompt", SYSTEM,
        "--strict-mcp-config",
        "--setting-sources", "",
        "--disable-slash-commands",
        "--no-session-persistence",
    ]
    env = os.environ.copy()
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
        timeout=900, env=env, cwd=str(MEDIA_DIR),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude terminó con código {proc.returncode}: {proc.stderr[-800:] or proc.stdout[-800:]}")
    return parse_claude_output(proc.stdout)


def parse_claude_output(stdout: str) -> dict[str, Any]:
    """Extrae el JSON estructurado de la salida de `claude -p --output-format json`."""
    envelope = json.loads(stdout)
    if isinstance(envelope, list):  # por si llega como lista de eventos
        envelope = next((e for e in reversed(envelope) if e.get("type") == "result"), envelope[-1])
    if envelope.get("is_error"):
        raise RuntimeError(f"Claude devolvió un error: {envelope.get('result')}")
    if isinstance(envelope.get("structured_output"), dict):
        return envelope["structured_output"]
    text = envelope.get("result", "")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("La respuesta de Claude no contiene JSON")
    return json.loads(text[start : end + 1])


def _excluded(raw: dict[str, Any], keywords: list[str]) -> bool:
    text = " ".join(str(raw.get(k, "")) for k in ("title", "summary", "details")).lower()
    for key in ("objectives", "sbcs", "evolutions", "modes", "events"):
        text += " " + " ".join(str(x.get("name", "")) for x in raw.get(key, []) or []).lower()
    return any(k.lower() in text for k in keywords)


def validate(result: dict[str, Any], tweets: list[Tweet],
             exclude: list[str] | None = None) -> tuple[list[Item], set[str], set[str]]:
    """Devuelve (novedades, ids_ignorados, ids_sin_tratar)."""
    ids = {t.id for t in tweets}
    media_by_tweet = {t.id: set(t.local_media) for t in tweets}
    items: list[Item] = []
    covered: set[str] = set()
    excluded_ids: set[str] = set()
    for raw in result.get("items", []):
        if raw.get("kind") not in KINDS or raw.get("source_type") not in ("official", "leak"):
            log.warning("Novedad descartada por tipo inválido: %s", raw.get("title"))
            continue
        raw["tweet_ids"] = [str(i) for i in raw.get("tweet_ids", []) if str(i) in ids]
        if not raw["tweet_ids"]:
            continue
        if exclude and _excluded(raw, exclude):
            log.info("Novedad descartada por tema excluido: %s", raw.get("title"))
            covered |= set(raw["tweet_ids"])
            excluded_ids |= set(raw["tweet_ids"])
            continue
        allowed = set().union(*(media_by_tweet[i] for i in raw["tweet_ids"]))
        imgs = [Path(x).name for x in raw.get("images", [])]
        raw["images"] = [x for x in dict.fromkeys(imgs) if x in allowed]
        if not raw["images"]:  # si Claude no eligió, usamos todas las de sus tweets
            raw["images"] = [x for i in raw["tweet_ids"] for x in next(t.local_media for t in tweets if t.id == i)]
        item = Item.from_analysis(raw)
        item.accounts = sorted({t.account for t in tweets if t.id in item.tweet_ids})
        item.urls = [t.url for t in tweets if t.id in item.tweet_ids]
        items.append(item)
        covered |= set(item.tweet_ids)
    ignored = ({str(i) for i in result.get("ignored_tweet_ids", [])} & ids) | excluded_ids
    missing = ids - covered - ignored
    return items, ignored - (covered - excluded_ids), missing


def analyze(cfg: Config, tweets: list[Tweet], state: dict[str, Any], recent_titles: list[str]):
    """Analiza en lotes. Genera (lote, items, ignorados, sin_tratar) o (lote, None, error)."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for i in range(0, len(tweets), cfg.batch_size):
        batch = tweets[i : i + cfg.batch_size]
        prompt = _build_prompt(batch, state, recent_titles, cfg.timezone)
        try:
            result = call_claude(prompt, cfg.claude_model, schema)
            items, ignored, missing = validate(result, batch, cfg.exclude_keywords)
            recent_titles = recent_titles + [it.title for it in items]
            yield batch, (items, ignored, missing), None
        except Exception as e:  # noqa: BLE001
            log.error("Fallo analizando lote: %s", e)
            yield batch, None, e
