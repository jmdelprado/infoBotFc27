"""Fuente alternativa: navegador Chromium sin ventana con la sesión de la cuenta del bot.

Abre el perfil de cada cuenta, captura las respuestas GraphQL `UserTweets` que hace la propia web
de X y las interpreta con el parser de twscrape.
"""

from __future__ import annotations

import logging

from ..models import Tweet
from .base import Source, SourceError, from_twscrape, parse_cookies

log = logging.getLogger(__name__)


class PlaywrightSource(Source):
    name = "playwright"

    def fetch(self, accounts: list[str], limit: int) -> list[Tweet]:
        from playwright.sync_api import sync_playwright
        from twscrape.models import parse_tweets

        cookies = parse_cookies(self.cfg.x_cookies)
        if "auth_token" not in cookies:
            raise SourceError("X_COOKIES debe incluir auth_token")

        out: list[Tweet] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 2000},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
            )
            ctx.add_cookies([
                {"name": k, "value": v, "domain": ".x.com", "path": "/", "secure": True}
                for k, v in cookies.items()
            ])
            page = ctx.new_page()
            for account in accounts:
                payloads: list[dict] = []

                def on_response(resp, payloads=payloads):
                    if "/UserTweets" in resp.url and resp.status == 200:
                        try:
                            payloads.append(resp.json())
                        except Exception:  # noqa: BLE001
                            pass

                page.on("response", on_response)
                try:
                    page.goto(f"https://x.com/{account}", wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(6000)
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(3000)
                finally:
                    page.remove_listener("response", on_response)

                seen: set[str] = set()
                for data in payloads:
                    for tw in parse_tweets(data):
                        if tw.id_str in seen:
                            continue
                        seen.add(tw.id_str)
                        t = from_twscrape(tw, account, self.cfg.include_self_replies)
                        if t:
                            out.append(t)
                log.info("Playwright @%s: %d tweets", account, len(seen))
            browser.close()
        if not out and accounts:
            raise SourceError("Playwright no capturó tweets (¿sesión caducada?)")
        return out
