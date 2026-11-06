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
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .config import MEDIA_DIR, Config
from .models import KINDS, SOURCE_TYPES, Item, Tweet

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("analysis.schema.json")

SYSTEM = """Eres el editor de "InfoBot FC 27", un grupo de Telegram en español sobre EA SPORTS FC 27 Ultimate Team.
Recibes tweets de cuentas de información muy fiables. El grupo se organiza en FICHAS: cada tema (una promo, un TOTW,
un SBC, una evolución…) tiene UNA sola ficha, que se va completando con cada novedad en lugar de repetir mensajes.

REGLAS
1. Solo interesan novedades de FC 27 Ultimate Team. Tipos (kind):
   - "promo": promos/equipos (Ultimate Scream, TOTW, Road to the Knockouts…), con todas sus cartas.
   - "card": cartas SUELTAS que no pertenecen a ninguna promo (mejoras de cartas dinámicas, cartas de jugador…).
   - "objective": objetivos (tareas con recompensa).
   - "sbc": desafíos de creación de plantillas.
   - "evolution": evoluciones (requisitos para meter la carta, coste, niveles y mejoras).
   - "mode": MODOS DE JUEGO para jugar: torneos, Rivals/Champions con recompensas especiales, Squad Battles
     especiales, drafts, eventos en directo jugables.
   - "event": el resto (mantenimientos, tienda/tokens, galería, packs, notas de parche relevantes para UT…).
   - DESCARTA SIEMPRE todo lo relacionado con "The Grounds" (objetivos, modo, recompensas…): va a ignored_tweet_ids.
   Lo demás (opiniones, encuestas, sorteos, bromas, quejas, autopromoción, otros juegos) va a ignored_tweet_ids.
2. NUNCA inventes datos. Si un dato no está en el texto ni en la imagen, no lo pongas. Copia las cifras tal cual.
3. MIRA TODAS LAS IMÁGENES con la herramienta Read: muchas veces la información (media, posición, requisitos,
   recompensas, fechas) solo está en la imagen. Transcribe lo que veas.
4. ETIQUETA (source_type). Las fuentes son fiables: lo que cuentan se da por hecho. NUNCA hables de "filtración",
   "rumor" ni "según fuentes"; escribe en afirmativo ("llega el viernes", "tendrá 91").
   - "official": ya está disponible en el juego, EA lo ha anunciado, o la fuente presenta los datos como los
     DEFINITIVOS que entrarán al juego (medias/stats finales, "official stats", "these are the final cards",
     el equipo confirmado con sus medias). Lo oficial va también al CALENDARIO, así que pon fechas.
   - "prediction": SOLO cuando la propia fuente lo presenta como predicción o estimación ("prediction",
     "predicted", "predicción", "could get", "possible upgrades", TOTW predicho, mejoras que podría recibir).
   - "none": todo lo demás (promos, cartas, SBC, evos o fechas que se esperan). Va sin etiqueta.
   Si una ficha mezcla datos definitivos y predichos, la etiqueta es la de la mayoría y en "cards" marca
   "predicted": true en cada carta predicha. Una ficha "official" nunca vuelve a "none" ni a "prediction".
5. FICHAS. Te doy las FICHAS ABIERTAS con su id y su contenido actual.
   - Si el tema ya tiene ficha → story_id = su id y devuelve la ficha COMPLETA ya actualizada: conserva todo lo que
     sigue siendo válido, añade lo nuevo y sustituye lo que haya cambiado (p. ej. una media predicha por la definitiva).
     El lector solo verá la ficha nueva, así que no puede faltar nada de la anterior.
   - Si es un tema nuevo → story_id = 0.
   - Si el tweet no aporta nada nuevo a su ficha → ignored_tweet_ids.
   - Agrupa: todo lo de una promo (equipos, cartas, mejoras, SBC y objetivos de la promo) va a la ficha de la promo;
     cada TOTW es una ficha; un SBC, una evolución o unos objetivos que no son de una promo tienen su propia ficha;
     lo de tienda/galería del mismo día va en una sola ficha; las mejoras de cartas dinámicas (+1, PS nuevos…)
     del mismo día van en una sola ficha ("Mejoras de cartas DD/MM").
   - Varios tweets del mismo tema en esta tanda → UNA sola entrada en items.
6. Todo en español de España, claro y natural. Los nombres propios (jugadores, promos, clubes) no se traducen.
   Posiciones SIEMPRE en español: POR, DFC, LD, LI, CAD, CAI, MCD, MC, MCO, MD, MI, ED, EI, SD, DC.
7. Campos de la ficha:
   - title: el NOMBRE del tema, estable (máx. 70 caracteres, sin emoji): "Road to the Knockouts", "TOTW 8",
     "SBC Lea Schüller 86", "Evolución Luiz Legacy". No es un titular de noticia.
   - summary: 1-2 frases con la situación ACTUAL del tema (qué es, cuándo, lo más importante).
   - key_facts: 2-6 pares etiqueta/valor (p. ej. "Inicio": "07/11 19:00", "Coste": "35.000"). No repitas aquí las
     cartas: ya salen en su lista.
   - cards: TODAS las cartas conocidas del tema (jugador, media, posición, club…). No las repitas en details.
   - details: el resto de información útil, completa y autosuficiente (el lector NO abre el tweet), en líneas que
     empiecen por "• ". Sin repetir el resumen ni la lista de cartas.
   - images: nombres de archivo de las imágenes NUEVAS útiles (exactamente como se te dan).
   - starts / ends: inicio y fin del tema si se conocen.
   - promo/objectives/sbcs/evolutions/modes/events: rellénalos cuando aplique; los oficiales alimentan el
     CALENDARIO. Pon fechas de inicio (start/starts) y fin (end/ends) SIEMPRE que se puedan deducir, en hora de
     España y en formato estricto "YYYY-MM-DD HH:MM" (o "YYYY-MM-DD"). Resuelve fechas relativas ("hasta el lunes",
     "next Friday 6PM UK", "ends in 3 days") usando la fecha actual y la fecha del tweet. Si no se pueden deducir,
     deja el campo vacío.
   - evolutions: requirements = requisitos para meter la carta; upgrades = mejoras que da; cost = coste.
8. Cada tweet_id de la entrada debe aparecer exactamente una vez: o en una novedad, o en ignored_tweet_ids.
"""

STORY_DETAILS_LIMIT = 1500


def story_context(story: Item) -> dict[str, Any]:
    """Contenido actual de una ficha tal y como se le enseña a Claude."""
    out: dict[str, Any] = {
        "story_id": story.id, "kind": story.kind, "source_type": story.source_type, "title": story.title,
        "summary": story.summary, "key_facts": story.key_facts,
        "details": story.details[:STORY_DETAILS_LIMIT],
    }
    for k in ("cards", "promo", "starts", "ends"):
        if story.extra.get(k):
            out[k] = story.extra[k]
    return out


def _build_prompt(tweets: list[Tweet], state: dict[str, Any], stories: list[Item], tz: str) -> str:
    now = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
    lines = [f"Fecha y hora actual (España): {now}", ""]
    lines.append("CALENDARIO OFICIAL ACTUAL (contexto):")
    lines.append(json.dumps(state.get("calendar", []), ensure_ascii=False)[:2500])
    lines.append("")
    lines.append("FICHAS ABIERTAS:")
    lines += [json.dumps(story_context(s), ensure_ascii=False) for s in stories] or ["(ninguna)"]
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


def validate(result: dict[str, Any], tweets: list[Tweet], exclude: list[str] | None = None,
             story_ids: set[int] | None = None) -> tuple[list[Item], set[str], set[str]]:
    """Devuelve (novedades, ids_ignorados, ids_sin_tratar). Un story_id desconocido se trata como ficha nueva."""
    ids = {t.id for t in tweets}
    media_by_tweet = {t.id: set(t.local_media) for t in tweets}
    items: list[Item] = []
    covered: set[str] = set()
    excluded_ids: set[str] = set()
    for raw in result.get("items", []):
        if raw.get("kind") not in KINDS or raw.get("source_type") not in SOURCE_TYPES:
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
        if item.story_id not in (story_ids or set()):
            item.story_id = None
        item.accounts = sorted({t.account for t in tweets if t.id in item.tweet_ids})
        item.urls = [t.url for t in tweets if t.id in item.tweet_ids]
        items.append(item)
        covered |= set(item.tweet_ids)
    ignored = ({str(i) for i in result.get("ignored_tweet_ids", [])} & ids) | excluded_ids
    missing = ids - covered - ignored
    return items, ignored - (covered - excluded_ids), missing


def analyze(cfg: Config, tweets: list[Tweet], state: dict[str, Any], open_stories: Callable[[], list[Item]]):
    """Analiza en lotes. Genera (lote, items, ignorados, sin_tratar) o (lote, None, error).
    open_stories se consulta en cada lote: así un lote ya ve las fichas creadas por el anterior."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for i in range(0, len(tweets), cfg.batch_size):
        batch = tweets[i : i + cfg.batch_size]
        stories = open_stories()
        prompt = _build_prompt(batch, state, stories, cfg.timezone)
        try:
            result = call_claude(prompt, cfg.claude_model, schema)
            items, ignored, missing = validate(result, batch, cfg.exclude_keywords, {s.id for s in stories})
            yield batch, (items, ignored, missing), None
        except Exception as e:  # noqa: BLE001
            log.error("Fallo analizando lote: %s", e)
            yield batch, None, e
