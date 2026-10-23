"""Interfaz común de las fuentes y conversión desde twscrape."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..models import Tweet


class SourceError(RuntimeError):
    pass


class Source(ABC):
    name = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def fetch(self, accounts: list[str], limit: int) -> list[Tweet]:
        """Devuelve los tweets más recientes de cada cuenta."""


def parse_cookies(raw: str) -> dict[str, str]:
    """'auth_token=..; ct0=..' (o JSON exportado por una extensión) → dict."""
    import json

    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("[") or raw.startswith("{"):
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
    out = {}
    for part in raw.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def from_twscrape(tw, account: str, include_self_replies: bool = True) -> Tweet | None:
    """Convierte un twscrape.models.Tweet en nuestro Tweet. Devuelve None si se descarta."""
    # Retuits: usamos el contenido original
    original = tw.retweetedTweet or tw
    if tw.inReplyToTweetIdStr and not include_self_replies:
        return None
    if tw.inReplyToUser and tw.inReplyToUser.username.lower() != account.lower():
        return None  # respuesta a otra persona: casi siempre ruido

    text = original.rawContent or ""
    if tw.retweetedTweet:
        text = f"[RT de @{original.user.username}] {text}"
    if original.quotedTweet:
        q = original.quotedTweet
        text += f"\n\n[Cita a @{q.user.username}]: {q.rawContent}"

    media: list[str] = []
    for src in (original, original.quotedTweet):
        if not src or not src.media:
            continue
        media += [p.url for p in src.media.photos]
        media += [v.thumbnailUrl for v in src.media.videos]
        media += [a.thumbnailUrl for a in src.media.animated if getattr(a, "thumbnailUrl", None)]

    return Tweet(
        id=tw.id_str,
        account=account,
        created_at=tw.date,
        text=text,
        url=tw.url,
        media=list(dict.fromkeys(media)),
    )
