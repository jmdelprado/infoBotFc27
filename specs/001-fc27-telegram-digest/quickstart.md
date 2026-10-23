# Quickstart

## Local (desarrollo)
```powershell
uv sync
uv run playwright install chromium
copy .env.example .env      # rellenar X_COOKIES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL
uv run python -m infobot preview --fixtures   # genera mensajes y portadas en out/ con tweets de ejemplo, sin publicar
uv run python -m infobot run --dry-run        # lee X de verdad y analiza, pero no publica
uv run python -m infobot run                  # ciclo completo
uv run pytest
```

## GitHub Actions
Secretos del repositorio: `X_COOKIES`, `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`
(opcional: `TELEGRAM_OWNER_CHAT_ID` para avisos de error).
El workflow `.github/workflows/infobot.yml` se ejecuta cada 4 horas; también se puede lanzar a mano desde la pestaña Actions.
