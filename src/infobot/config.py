"""Configuración: config.yaml + variables de entorno (.env en local)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
MEDIA_DIR = DATA_DIR / "media"
OUT_DIR = ROOT / "out"
ASSETS_DIR = ROOT / "assets"


def _load_dotenv(path: Path) -> None:
    """Carga un .env sencillo sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


@dataclass
class Config:
    accounts: list[str]
    tweets_per_account: int = 40
    first_run_hours: int = 24
    include_self_replies: bool = True
    claude_model: str = "sonnet"
    batch_size: int = 12
    show_source_link: bool = True
    channel_title: str = "InfoBot FC 27"
    timezone: str = "Europe/Madrid"
    # Temas que se descartan siempre (no se publican ni entran en el calendario)
    exclude_keywords: list[str] = field(default_factory=lambda: ["the grounds"])
    # Orden en que se prueban las fuentes de X
    sources: list[str] = field(default_factory=lambda: ["syndication", "twscrape", "playwright"])
    # Secretos
    x_cookies: str = field(default="", repr=False)
    telegram_token: str = field(default="", repr=False)
    telegram_channel: str = ""
    telegram_owner_chat_id: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        _load_dotenv(ROOT / ".env")
        raw = yaml.safe_load((path or ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        accounts = [a.lstrip("@").strip() for a in raw.pop("accounts", []) if a]
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(
            accounts=accounts,
            **known,
            # .strip(): al pegar los secretos en GitHub es fácil que se cuele un salto de línea
            x_cookies=os.environ.get("X_COOKIES", "").strip(),
            telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_channel=os.environ.get("TELEGRAM_CHANNEL", "").strip(),
            telegram_owner_chat_id=os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip(),
        )
