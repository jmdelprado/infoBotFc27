# Implementation Plan: Resumen de novedades de FC 27 en Telegram

**Branch**: `001-fc27-telegram-digest` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fc27-telegram-digest/spec.md`

## Summary

Un proceso por lotes en Python que se ejecuta cada 4 horas en GitHub Actions. Recoge los tweets nuevos de las
cuentas configuradas con `twscrape` (o con Playwright si falla), descarga las imágenes y pide a Claude Code en
modo no interactivo (`claude -p --json-schema`) que clasifique y extraiga los datos de texto e imágenes. Después
fusiona el resultado con el estado actual, genera una portada PNG con una plantilla HTML (Playwright) y publica
álbum + texto en un canal de Telegram mediante la Bot API. El estado (SQLite + JSON) se guarda en el propio
repositorio con un commit en cada ejecución.

## Technical Context

**Language/Version**: Python 3.12 (gestionado con uv)

**Primary Dependencies**: twscrape 0.20 (lectura de X), playwright 1.64 (fuente alternativa + portadas),
httpx (Bot API de Telegram y descarga de imágenes), jinja2 (plantillas de mensajes y portadas), pyyaml (configuración),
Claude Code CLI 2.x (análisis, con `CLAUDE_CODE_OAUTH_TOKEN`)

**Storage**: `data/infobot.db` (SQLite: tweets, novedades, publicaciones) + `data/state.json` (estado actual legible)

**Testing**: pytest (lógica pura: parseo, fusión de estado, formato de Telegram, partición de mensajes)

**Target Platform**: GitHub Actions `ubuntu-latest` (y Windows en local para desarrollo)

**Project Type**: CLI / proceso por lotes (`python -m infobot run|daily|preview`)

**Performance Goals**: un ciclo completo en menos de 5 minutos con unos 20 tweets nuevos

**Constraints**: 0 €; menos de 2000 min/mes de Actions (≈ 6 × 4 min × 30 = 720 min); límites de Telegram
(caption ≤ 1024, texto ≤ 4096, álbum ≤ 10 fotos, ~20 mensajes/min por canal)

**Scale/Scope**: 2 cuentas al principio (hasta ~20), decenas de tweets al día

## Constitution Check

| Principio | Cumplimiento |
|---|---|
| I. Coste cero | ✅ twscrape/Playwright (gratis), Claude Code con suscripción, Actions en cuota gratuita, Telegram gratuito |
| II. Autosuficiente | ✅ El álbum lleva las imágenes originales + el texto completo traducido/resumido + datos clave |
| III. Fidelidad | ✅ El prompt prohíbe inventar; el esquema JSON obliga a `source_type` (oficial/filtración) |
| IV. Sin duplicados | ✅ Tabla `tweets` con id único y estado; `posts` evita reenviar una misma novedad |
| V. Resiliencia | ✅ Interfaz `Source` con fallback; los tweets solo se marcan como procesados tras publicarse |
| VI. Simplicidad | ✅ Un paquete, SQLite, sin servidores |

Re-evaluación tras el diseño: sin violaciones. No hace falta la tabla de complejidad.

## Project Structure

### Documentation (this feature)

```text
specs/001-fc27-telegram-digest/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── analysis.schema.json     # salida estructurada que debe devolver Claude
│   └── telegram-message.md      # plantilla de los mensajes del canal
└── tasks.md                     # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
config.yaml                      # cuentas, canal, límites
pyproject.toml
src/infobot/
├── __main__.py                  # CLI: run | daily | preview | login-check
├── config.py
├── models.py                    # dataclasses Tweet, Item, State
├── db.py                        # SQLite
├── sources/
│   ├── base.py                  # interfaz Source
│   ├── twscrape_source.py
│   └── playwright_source.py
├── media.py                     # descarga de imágenes
├── analyzer.py                  # llamada a `claude -p` + prompt + validación
├── state.py                     # fusión del estado actual
├── render/
│   ├── telegram_format.py       # texto HTML de Telegram
│   ├── cover.py                 # portada PNG (Playwright)
│   └── templates/               # cover.html.j2, item.html.j2, pinned.html.j2, daily.html.j2
├── telegram.py                  # cliente de la Bot API
└── pipeline.py                  # orquestación del ciclo
assets/fonts/                    # fuentes OFL incluidas en el repositorio
data/                            # infobot.db, state.json (con commit desde Actions)
tests/
├── fixtures/
└── test_*.py
.github/workflows/infobot.yml
```

**Structure Decision**: un único proyecto (opción 1) con paquete `src/infobot`.

## Complexity Tracking

Sin violaciones.
