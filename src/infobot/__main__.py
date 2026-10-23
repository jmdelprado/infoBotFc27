"""CLI de InfoBot.

    python -m infobot run [--dry-run]         ciclo completo (cada 4 h en GitHub Actions)
    python -m infobot daily [--dry-run]       resumen de las últimas 24 h
    python -m infobot preview [--claude]      vista previa con tweets de ejemplo (out/preview.html)
    python -m infobot check                   comprueba la configuración y las credenciales
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import MEDIA_DIR, OUT_DIR, ROOT, Config

FIXTURES = ROOT / "tests" / "fixtures"


def load_fixture_tweets():
    import shutil

    from .models import Tweet

    raw = json.loads((FIXTURES / "tweets.json").read_text(encoding="utf-8"))
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    tweets = []
    for i, t in enumerate(raw):
        for name in t.get("local_media", []):
            shutil.copy(FIXTURES / "media" / name, MEDIA_DIR / name)
        tweets.append(Tweet(
            id=t["id"], account=t["account"], created_at=now - timedelta(minutes=30 * (len(raw) - i)),
            text=t["text"], url=t["url"], media=[], local_media=t.get("local_media", []),
        ))
    return tweets


def _notify_owner(cfg: Config, text: str) -> None:
    if not (cfg.telegram_token and cfg.telegram_owner_chat_id):
        return
    try:
        from .telegram import Telegram

        Telegram(cfg.telegram_token, cfg.telegram_owner_chat_id).notify(cfg.telegram_owner_chat_id, text)
    except Exception:  # noqa: BLE001
        logging.exception("No se pudo avisar al propietario")


def cmd_check(cfg: Config) -> int:
    import shutil

    from .sources.base import parse_cookies

    ok = True

    def line(good: bool, msg: str) -> None:
        nonlocal ok
        ok &= good
        print(("✅ " if good else "❌ ") + msg)

    line(bool(cfg.accounts), f"Cuentas a seguir: {', '.join('@' + a for a in cfg.accounts) or 'ninguna'}")
    c = parse_cookies(cfg.x_cookies)
    line({"auth_token", "ct0"} <= c.keys(), "X_COOKIES con auth_token y ct0")
    line(bool(shutil.which("claude")), "Claude Code CLI instalado")
    line(bool(cfg.telegram_token), "TELEGRAM_BOT_TOKEN definido")
    line(bool(cfg.telegram_channel), f"TELEGRAM_CHANNEL definido ({cfg.telegram_channel or '-'})")
    if cfg.telegram_token and cfg.telegram_channel:
        try:
            import httpx

            r = httpx.get(f"https://api.telegram.org/bot{cfg.telegram_token}/getChat",
                          params={"chat_id": cfg.telegram_channel}, timeout=20).json()
            line(r.get("ok", False), f"El bot ve el canal: {r.get('result', {}).get('title') or r.get('description')}")
        except Exception as e:  # noqa: BLE001
            line(False, f"Telegram: {e}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "twscrape"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(prog="infobot")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true", help="no publica; genera out/preview.html")
    d = sub.add_parser("daily")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--force", action="store_true")
    pv = sub.add_parser("preview")
    pv.add_argument("--claude", action="store_true", help="analiza los ejemplos con Claude de verdad")
    sub.add_parser("check")
    args = p.parse_args(argv)

    cfg = Config.load()
    from . import pipeline

    try:
        if args.cmd == "check":
            return cmd_check(cfg)
        if args.cmd == "run":
            res = pipeline.run(cfg, dry_run=args.dry_run)
        elif args.cmd == "daily":
            res = pipeline.daily(cfg, dry_run=args.dry_run, force=args.force)
        else:  # preview
            override = None if args.claude else json.loads((FIXTURES / "analysis.json").read_text(encoding="utf-8"))
            res = pipeline.run(
                cfg, dry_run=True, tweets=load_fixture_tweets(), analysis_override=override,
                db_path=OUT_DIR / "_empty.db",
            )
            Path(OUT_DIR / "_empty.db").unlink(missing_ok=True)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        logging.exception("InfoBot ha fallado")
        _notify_owner(cfg, f"⚠️ InfoBot ha fallado ({args.cmd}): {e}\n\n{traceback.format_exc()[-1500:]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
