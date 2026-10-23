"""Fuentes de tweets. Se prueba cada una en orden hasta que una funciona."""

from __future__ import annotations

import logging

from ..config import Config
from ..models import Tweet
from .base import Source, SourceError

log = logging.getLogger(__name__)


def fetch_all(cfg: Config) -> list[Tweet]:
    from .playwright_source import PlaywrightSource
    from .syndication_source import SyndicationSource
    from .twscrape_source import TwscrapeSource

    available = {"syndication": SyndicationSource, "twscrape": TwscrapeSource, "playwright": PlaywrightSource}
    sources: list[Source] = [available[n](cfg) for n in cfg.sources if n in available]
    errors = []
    for src in sources:
        try:
            tweets = src.fetch(cfg.accounts, cfg.tweets_per_account)
            log.info("Fuente %s: %d tweets", src.name, len(tweets))
            return tweets
        except Exception as e:  # noqa: BLE001 - probamos la siguiente fuente
            log.warning("Fuente %s ha fallado: %s", src.name, e)
            errors.append(f"{src.name}: {e}")
    raise SourceError("Todas las fuentes han fallado → " + " | ".join(errors))


__all__ = ["fetch_all", "Source", "SourceError"]
