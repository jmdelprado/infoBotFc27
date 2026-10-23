# Research: InfoBot

## 1. Lectura de X sin coste
- **Decision**: `twscrape` 0.20.1 (agosto de 2026, mantenido), iniciando sesión con las cookies `auth_token` y `ct0` de `@infobotfc`
  (`AccountsPool.add_account(..., cookies="auth_token=...; ct0=...")`). Se usa `user_by_login` → `user_tweets(uid, limit)`.
- **Rationale**: usa la API GraphQL interna de X; es rápido y devuelve texto completo (incluidos los tweets largos) y medios.
  Con cookies no hace falta guardar la contraseña ni pasar el 2FA.
- **Fallback**: Playwright con las mismas cookies: abre `x.com/<cuenta>`, intercepta las respuestas `UserTweets` y las parsea
  con el parser de twscrape.
- **Alternatives considered**: API oficial (de pago, descartada); Nitter (instancias caídas); servicios externos (de pago o de prueba).
- **Riesgo**: X puede bloquear las IP de GitHub. Mitigación: el workflow avisa y se puede ejecutar la recogida en local.

## 2. Análisis con IA sin coste
- **Decision**: Claude Code CLI `claude -p` con `--output-format json --json-schema <schema> --tools Read --model sonnet`,
  autenticado con `CLAUDE_CODE_OAUTH_TOKEN` (generado con `claude setup-token`). Las imágenes se pasan como rutas locales y Claude las lee con `Read`.
- **Rationale**: cubre visión + salida estructurada validada y consume la suscripción, no la API de pago.
- **Lote**: todos los tweets nuevos de un ciclo van en una sola llamada (menos consumo); si son más de 15, se dividen en lotes.

## 3. Portadas
- **Decision**: plantilla HTML/CSS (Jinja2) renderizada a PNG 1280×720 con Playwright Chromium; fuentes OFL (Oswald, Inter) incluidas en el repositorio.
- **Alternatives**: Pillow (más rápido, pero diseñarlo cuesta más). Chromium ya se instala para la fuente alternativa.

## 4. Telegram
- **Decision**: Bot API con httpx: `sendMediaGroup` (portada + hasta 9 imágenes; caption corto en la primera) seguido de
  `sendMessage` con el texto completo en `parse_mode=HTML`, usando `<blockquote expandable>` para los detalles.
  El mensaje fijado se crea una vez (`pinChatMessage`) y luego se edita (`editMessageText`).
- **Rationale**: el caption de un álbum está limitado a 1024 caracteres; el texto aparte permite hasta 4096 y se divide si hace falta.

## 5. Ejecución y persistencia
- **Decision**: GitHub Actions `cron: "7 */4 * * *"` (minuto 7 para evitar la congestión de la hora en punto) + `workflow_dispatch`;
  resumen diario en `cron: "0 20 * * *"` (22:00 hora de España en verano). Al terminar, se hace commit de `data/` con `[skip ci]`.
  `concurrency` evita que se solapen dos ejecuciones.
- **Rationale**: no hace falta un servidor ni una base de datos externa; el historial queda guardado en git.
