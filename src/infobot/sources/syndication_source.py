"""Fuente "syndication": el servicio de X que alimenta los timelines incrustados en webs.

- Lista de tweets: syndication.twitter.com/srv/timeline-profile/screen-name/<cuenta> (con las cookies del bot).
- Tweet completo: cdn.syndication.twimg.com/tweet-result?id=...&token=... (sin sesión), para recuperar
  el texto completo y las imágenes de los retuits, que en la lista llegan recortados.

Usa servidores distintos de la API interna de X, que bloquea las IPs de centros de datos como las de GitHub.
"""

from __future__ import annotations

import email.utils
import json
import logging
import math
import re

import httpx

from ..models import Tweet
from .base import Source, SourceError, parse_cookies

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
TIMELINE = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{}"
TWEET = "https://cdn.syndication.twimg.com/tweet-result"
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
STATUS_ID = re.compile(r"/status/(\d+)")


def tweet_token(tweet_id: str) -> str:
    """Token que pide tweet-result: ((id / 1e15) * π) en base 36, sin ceros ni punto."""
    x = (int(tweet_id) / 1e15) * math.pi
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ip, fp, s = int(x), x - int(x), ""
    while ip:
        s, ip = digits[ip % 36] + s, ip // 36
    s = (s or "0") + "."
    for _ in range(12):
        fp *= 36
        d = int(fp)
        s += digits[d]
        fp -= d
    return re.sub(r"(0+|\.)", "", s)


def _media(t: dict) -> list[str]:
    urls: list[str] = []
    for key in ("extended_entities", "entities"):
        for m in (t.get(key) or {}).get("media", []) or []:
            if m.get("media_url_https"):
                urls.append(m["media_url_https"])
    return list(dict.fromkeys(urls))


def parse_timeline(html: str) -> list[dict]:
    m = NEXT_DATA.search(html)
    if not m:
        raise SourceError("La respuesta de syndication no contiene datos (¿sesión caducada?)")
    data = json.loads(m.group(1))
    entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
    return [e["content"]["tweet"] for e in entries if e.get("type") == "tweet" and e.get("content", {}).get("tweet")]


class SyndicationSource(Source):
    name = "syndication"

    def fetch(self, accounts: list[str], limit: int) -> list[Tweet]:
        cookies = parse_cookies(self.cfg.x_cookies)
        if "auth_token" not in cookies:
            raise SourceError("X_COOKIES debe incluir auth_token")
        out: list[Tweet] = []
        errors = []
        with httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=True) as client:
            for account in accounts:
                r = client.get(TIMELINE.format(account), cookies=cookies)
                if r.status_code != 200:
                    errors.append(f"@{account}: HTTP {r.status_code}")
                    continue
                raw = parse_timeline(r.text)[:limit]
                n = 0
                for t in raw:
                    tw = self._convert(client, t, account)
                    if tw:
                        out.append(tw)
                        n += 1
                log.info("Syndication @%s: %d tweets", account, n)
        if not out:
            raise SourceError("syndication no devolvió tweets: " + "; ".join(errors or ["lista vacía"]))
        return out

    def _full_tweet(self, client: httpx.Client, tweet_id: str) -> dict | None:
        try:
            r = client.get(TWEET, params={"id": tweet_id, "token": tweet_token(tweet_id), "lang": "es"})
            return r.json() if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None

    def _convert(self, client: httpx.Client, t: dict, account: str) -> Tweet | None:
        reply_to = t.get("in_reply_to_screen_name")
        if reply_to and reply_to.lower() != account.lower():
            return None
        if reply_to and not self.cfg.include_self_replies:
            return None

        text = t.get("full_text") or t.get("text") or ""
        media = _media(t)

        # Retuit: la lista trae el texto recortado; se recupera el original completo si se conoce su id
        if text.startswith("RT @"):
            original_id = next(
                (STATUS_ID.search(m.get("expanded_url", "")).group(1)
                 for m in (t.get("entities") or {}).get("media", []) or []
                 if STATUS_ID.search(m.get("expanded_url", ""))),
                None,
            )
            full = self._full_tweet(client, original_id) if original_id else None
            if full:
                author = (full.get("user") or {}).get("screen_name", "?")
                text = f"[RT de @{author}] {full.get('text', '')}"
                media = [m["media_url_https"] for m in full.get("mediaDetails", []) if m.get("media_url_https")] or media

        quoted = t.get("quoted_status")
        if quoted:
            qa = (quoted.get("user") or {}).get("screen_name", "?")
            text += f"\n\n[Cita a @{qa}]: {quoted.get('full_text') or quoted.get('text') or ''}"
            media += [u for u in _media(quoted) if u not in media]

        permalink = t.get("permalink") or f"/{account}/status/{t['id_str']}"
        return Tweet(
            id=t["id_str"],
            account=account,
            created_at=email.utils.parsedate_to_datetime(t["created_at"]),
            text=text,
            url=f"https://x.com{permalink}" if permalink.startswith("/") else permalink,
            media=media,
        )
