# Tasks: Resumen de novedades de FC 27 en Telegram

**Input**: plan.md, spec.md, data-model.md, contracts/

## Phase 1: Setup
- [x] T001 Crear `pyproject.toml` (uv, Python 3.12, dependencias), `.gitignore`, `.env.example`, `config.yaml`
- [x] T002 [P] Descargar las fuentes OFL a `assets/fonts/`
- [x] T003 [P] Crear el paquete `src/infobot/` y `tests/`

## Phase 2: Foundational
- [x] T004 `config.py`: cargar `config.yaml` + variables de entorno
- [x] T005 `models.py`: dataclasses Tweet, Item
- [x] T006 `db.py`: esquema SQLite y operaciones (upsert de tweets, pendientes, items, posts, meta)
- [x] T007 [P] `sources/base.py` + `sources/twscrape_source.py` + `sources/playwright_source.py`
- [x] T008 [P] `media.py`: descargar imágenes (`name=large`) a `data/media/`

## Phase 3: US1 — Novedades en el canal (P1) 🎯 MVP
- [x] T009 [US1] `analysis.schema.json` + `analyzer.py` (prompt, lotes, `claude -p`, validación, reintentos)
- [x] T010 [US1] `telegram.py`: sendMediaGroup, sendMessage, edit, pin, gestión del error 429
- [x] T011 [US1] `render/telegram_format.py`: plantilla de la novedad, escape HTML, partición de textos
- [x] T012 [US1] `pipeline.py` ciclo `run` (fetch → store → analyze → post → mark done), `--dry-run`
- [x] T013 [US1] Tests: formato, partición, deduplicación (db), parseo de la salida del analizador

## Phase 4: US2 — Estado fijado (P2)
- [x] T014 [US2] `state.py`: fusión + caducidad + límites
- [x] T015 [US2] Plantilla del fijado y creación/edición en `pipeline.py`
- [x] T016 [US2] Tests de `state.py`

## Phase 5: US3 — Estilo (P2)
- [x] T017 [US3] `render/templates/cover.html.j2` + `render/cover.py` (Playwright → PNG)
- [x] T018 [US3] Comando `preview --fixtures` que genera `out/` (HTML de vista previa + PNG)
- [x] T019 [US3] Logo/avatar del canal `assets/avatar.png` y texto de descripción

## Phase 6: US4 — Resumen diario (P3)
- [x] T020 [US4] Comando `daily` + plantilla + test

## Phase 7: Polish
- [x] T021 `.github/workflows/infobot.yml` (cron cada 4 h, daily, commit de `data/`, concurrency)
- [x] T022 `README.md` en español con la guía de puesta en marcha (BotFather, cookies, setup-token, secretos)
- [x] T023 Ejecutar pytest + preview y revisar las portadas visualmente

## Dependencies
Setup → Foundational → US1 → (US2, US3 en paralelo) → US4 → Polish.
