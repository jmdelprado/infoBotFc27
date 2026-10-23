"""Fuente principal: twscrape (API interna de X) con las cookies de la cuenta del bot."""

from __future__ import annotations

import asyncio
import logging
import os

from ..config import DATA_DIR
from ..models import Tweet
from .base import Source, SourceError, from_twscrape, parse_cookies

log = logging.getLogger(__name__)


class TwscrapeSource(Source):
    name = "twscrape"

    def fetch(self, accounts: list[str], limit: int) -> list[Tweet]:
        return asyncio.run(self._fetch(accounts, limit))

    async def _fetch(self, accounts: list[str], limit: int) -> list[Tweet]:
        from twscrape import API

        cookies = parse_cookies(self.cfg.x_cookies)
        if not {"auth_token", "ct0"} <= cookies.keys():
            raise SourceError("X_COOKIES debe incluir auth_token y ct0")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        api = API(str(DATA_DIR / "accounts.db"), raise_when_no_account=True)
        bot_user = os.environ.get("X_USERNAME", "infobotfc")
        await api.pool.add_account_cookies(bot_user, "; ".join(f"{k}={v}" for k, v in cookies.items()))

        out: list[Tweet] = []
        for account in accounts:
            user = await api.user_by_login(account)
            if not user:
                log.warning("No se encuentra la cuenta @%s", account)
                continue
            n = 0
            async for tw in api.user_tweets(user.id, limit=limit):
                t = from_twscrape(tw, account, self.cfg.include_self_replies)
                if t:
                    out.append(t)
                n += 1
                if n >= limit:
                    break
        if not out and accounts:
            raise SourceError("twscrape no devolvió ningún tweet (¿cookies caducadas o bloqueo?)")
        return out
