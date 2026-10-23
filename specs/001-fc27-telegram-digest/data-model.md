# Data Model

## SQLite `data/infobot.db`

### tweets
| campo | tipo | nota |
|---|---|---|
| id | TEXT PK | id_str de X |
| account | TEXT | cuenta seguida |
| created_at | TEXT ISO | |
| text | TEXT | texto completo (incluye el del tweet citado) |
| url | TEXT | |
| media_json | TEXT | lista de URLs de imágenes (fotos y miniaturas de vídeo) |
| status | TEXT | `pending` · `done` · `ignored` · `failed` |
| attempts | INT | reintentos de análisis (máx. 3) |
| fetched_at | TEXT ISO | |

### items (novedades)
| campo | tipo | nota |
|---|---|---|
| id | INTEGER PK | |
| kind | TEXT | `promo` · `card` · `objective` · `sbc` · `event` |
| source_type | TEXT | `official` · `leak` |
| title | TEXT | |
| summary | TEXT | resumen en español |
| details | TEXT | texto completo traducido/desarrollado |
| data_json | TEXT | datos estructurados (cartas, requisitos, fechas…) |
| tweet_ids | TEXT | JSON con los tweets de origen |
| images_json | TEXT | rutas locales de las imágenes |
| created_at | TEXT ISO | |
| posted | INT | 0/1 |

### posts
| campo | tipo | nota |
|---|---|---|
| item_id | INT FK | NULL para el fijado o el resumen diario |
| kind | TEXT | `item` · `pinned` · `daily` |
| message_ids | TEXT | JSON |
| posted_at | TEXT ISO | |

### meta
clave/valor: `pinned_message_id`, `last_daily_at`, `first_run_at`.

## `data/state.json` (estado actual)
```json
{
  "updated_at": "ISO",
  "active_promo": {"name": "", "source_type": "official|leak", "start": "", "end": "", "notes": ""},
  "objectives": [{"name": "", "reward": "", "ends": "", "source_type": ""}],
  "sbcs": [{"name": "", "reward": "", "ends": "", "source_type": ""}],
  "recent_cards": [{"player": "", "rating": 0, "position": "", "club": "", "promo": "", "source_type": ""}],
  "recent_leaks": [{"title": "", "date": ""}]
}
```
Reglas: las listas se limitan (cartas 15, filtraciones 10); se quitan los elementos cuyo `ends` ya ha pasado;
una novedad oficial sustituye a una filtración con el mismo nombre.
