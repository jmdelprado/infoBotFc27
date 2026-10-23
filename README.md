# InfoBot FC 27

Bot que lee las cuentas de X sobre EA SPORTS FC 27 Ultimate Team, las analiza con Claude (texto **e imágenes**)
y publica en un **grupo de Telegram con secciones (Temas)** las novedades: promos, cartas nuevas, objetivos, SBCs,
evoluciones, eventos y filtraciones, además de un **calendario** con todo lo que hay para hacer y jugar.

Secciones: 📌 General (estado actual fijado) · 🔥 Promos · 🃏 Cartas · 🎯 Objetivos · 🧩 SBC · 🧬 Evoluciones ·
📢 Eventos · 🕵️ Filtraciones · 📅 Calendario · 🗞️ Resumen diario. El bot las crea solo la primera vez.

- Se ejecuta solo **cada 4 horas** en GitHub Actions (el PC puede estar apagado) y publica un **resumen diario**.
- Cada novedad lleva una **portada propia**, las imágenes originales y el texto completo en español.
- Un **mensaje fijado** muestra el estado actual (promo activa, objetivos, SBCs, últimas cartas y filtraciones).
- **Coste 0 €**: sin APIs de pago. Usa tu suscripción de Claude, la cuota gratuita de GitHub y Telegram.

Cuentas que sigue: `config.yaml` → `accounts` (ahora `@JuniorSintress` y `@FutPoliceLeaks`).

---

## Puesta en marcha (una sola vez, unos 15 minutos)

### 1. Crear el bot y el grupo de Telegram
1. En Telegram, abre **@BotFather** → `/newbot` → nombre `InfoBot FC 27` → usuario terminado en `bot`.
   Copia el **token** que te da (algo como `123456:ABC...`).
2. Crea un **grupo** → en su configuración activa **Temas** (Topics). Ponle como foto `assets/avatar.png`.
   Descripción sugerida: *"Promos, cartas, objetivos, SBCs, evoluciones y filtraciones de FC 27 Ultimate Team, al momento y en español. 🔥🃏🎯🧩🧬"*
3. Añade el bot como **administrador** con permisos para **gestionar temas, enviar, editar y fijar mensajes**.
4. Permisos del grupo → desactiva "Enviar mensajes" para los miembros, así solo publica el bot.
5. Escribe un mensaje en el grupo y ejecuta `uv run python -m infobot chat-id`: te da el número para `TELEGRAM_CHANNEL`.
4. (Opcional, para recibir avisos si algo falla) Escribe a tu bot por privado y abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates`: tu número de chat aparece en `"chat":{"id": ...}`.

### 2. Sacar las cookies de la cuenta de X `@infobotfc`
1. En el navegador, inicia sesión en x.com con **@infobotfc** (nunca con tu cuenta personal).
2. Pulsa F12 → pestaña **Aplicación** (Application) → Cookies → `https://x.com`.
3. Copia los valores de `auth_token` y `ct0` y forma este texto:
   `auth_token=XXXXXXXX; ct0=YYYYYYYY`
4. No cierres la sesión desde ese navegador (si lo haces, las cookies dejan de valer y hay que repetir esto).

### 3. Token de Claude
En una terminal: `claude setup-token` → inicia sesión con tu cuenta de Claude → copia el token (`sk-ant-oat...`).

### 4. Secretos en GitHub
Repositorio → **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `X_COOKIES` | `auth_token=...; ct0=...` |
| `CLAUDE_CODE_OAUTH_TOKEN` | el token del paso 3 |
| `TELEGRAM_BOT_TOKEN` | el token de BotFather |
| `TELEGRAM_CHANNEL` | número del grupo (`-100...`, sale con `chat-id`) |
| `TELEGRAM_OWNER_CHAT_ID` | (opcional) tu número de chat |

### 5. Probar
Pestaña **Actions → InfoBot → Run workflow**: primero con `check` (comprueba todo) y luego con `run`.
A partir de ahí funciona solo cada 4 horas.

---

## Uso en local (opcional)

```powershell
uv sync
uv run playwright install chromium
copy .env.example .env          # y rellénalo
uv run python -m infobot check  # comprueba la configuración
uv run python -m infobot preview          # vista previa con ejemplos → out/preview.html
uv run python -m infobot run --dry-run    # lee X y analiza de verdad, pero NO publica
uv run python -m infobot run              # ciclo completo
uv run python -m infobot daily --force    # resumen diario
uv run pytest
```

## Cómo funciona

```
X (twscrape → si falla, navegador Playwright)
  → data/infobot.db (tweets vistos, sin duplicados) + descarga de imágenes
  → Claude Code (`claude -p`, lee texto + imágenes, devuelve JSON validado)
  → novedades → portada PNG + álbum + texto en Telegram
  → data/state.json (estado actual) → mensaje fijado
```

Si un paso falla, los tweets no se pierden: se reintentan en la siguiente ejecución (máx. 3 veces).

## Problemas habituales
- **"Todas las fuentes han fallado"**: las cookies de X han caducado o X ha bloqueado la IP de GitHub.
  Repite el paso 2 y actualiza `X_COOKIES`.
- **Error de Claude**: el token ha caducado → repite el paso 3.
- **"chat not found" en Telegram**: el bot no es administrador del grupo o `TELEGRAM_CHANNEL` está mal escrito.
- **No se crean las secciones**: activa Temas en el grupo y da al bot el permiso "Gestionar temas".

## Desarrollo
Proyecto creado con [spec-kit](https://github.com/github/spec-kit): las reglas del proyecto están en
`.specify/memory/constitution.md` y la especificación, el plan y las tareas en `specs/001-fc27-telegram-digest/`.

Aviso: leer X sin su API oficial va contra sus condiciones de uso; por eso el bot usa una cuenta secundaria.
Proyecto no oficial, sin relación con EA SPORTS.
