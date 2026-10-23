"""Descarga de imágenes de los tweets."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import MEDIA_DIR
from .models import Tweet

log = logging.getLogger(__name__)


def _large(url: str) -> str:
    # pbs.twimg.com admite ?name=large para la máxima resolución razonable
    if "pbs.twimg.com" in url and "name=" not in url:
        return url + ("&" if "?" in url else "?") + "name=large"
    return url


def download_media(tweets: list[Tweet], client: httpx.Client | None = None) -> None:
    """Descarga las imágenes de cada tweet en data/media/<tweet_id>_<n>.<ext> y rellena local_media (solo nombres de archivo)."""
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        for t in tweets:
            if not t.media:  # nada remoto que descargar: se conserva lo que ya hubiera en local
                continue
            paths: list[str] = []
            for n, url in enumerate(t.media):
                ext = Path(urlparse(url).path).suffix or ".jpg"
                dest = MEDIA_DIR / f"{t.id}_{n}{ext}"
                if not dest.exists():
                    try:
                        r = client.get(_large(url))
                        r.raise_for_status()
                        dest.write_bytes(r.content)
                    except httpx.HTTPError as e:
                        log.warning("No se pudo descargar %s: %s", url, e)
                        continue
                paths.append(dest.name)
            t.local_media = paths
    finally:
        if own:
            client.close()
