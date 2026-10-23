"""Portadas PNG (1280×720) con estilo FC, generadas con una plantilla HTML y Chromium (Playwright)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import ASSETS_DIR, MEDIA_DIR
from ..models import Item

TEMPLATES = Path(__file__).with_name("templates")
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))

COLORS = {
    "promo": ("#ff7a18", "#b3001b"),
    "card": ("#f7d774", "#8a6a12"),
    "objective": ("#2bd67b", "#0b5d3b"),
    "sbc": ("#36a2ff", "#1032a3"),
    "event": ("#b26bff", "#4b1a8f"),
    "daily": ("#ff3d7f", "#2a1460"),
}


def _title_size(title: str, wide: bool) -> int:
    n = len(title)
    base = 92 if wide else 80
    if n > 55:
        return base - 34
    if n > 38:
        return base - 22
    if n > 24:
        return base - 10
    return base


def cover_html(
    *, kind: str, title: str, emoji: str, label: str, source_type: str | None,
    facts: list[dict[str, str]], hero: Path | None, brand: str, footer: str,
) -> str:
    c1, c2 = COLORS.get(kind, COLORS["event"])
    facts = [f for f in facts if f.get("value")][:4]
    return _env.get_template("cover.html.j2").render(
        fonts=(ASSETS_DIR / "fonts").resolve().as_uri(),
        c1=c1, c2=c2, emoji=emoji, label=label, title=title, brand=brand, footer=footer,
        source_label={"official": "✅ Oficial", "leak": "🕵️ Filtración"}.get(source_type or "", ""),
        source_class=source_type or "",
        facts=facts, fact_cols=min(max(len(facts), 1), 2 if hero else 4),
        hero=hero.resolve().as_uri() if hero else None,
        has_hero=True, show_emoji=True,
        title_size=_title_size(title, wide=False),
    )


def item_cover_html(item: Item, brand: str) -> str:
    hero = next((MEDIA_DIR / n for n in item.images if (MEDIA_DIR / n).exists()), None)
    return cover_html(
        kind=item.kind, title=item.title, emoji=item.meta["emoji"], label=item.meta["label"],
        source_type=item.source_type, facts=item.key_facts, hero=hero, brand=brand,
        footer=f"{brand} · {datetime.now():%d/%m/%Y}",
    )


def daily_cover_html(items: list[Item], brand: str, date_label: str) -> str:
    counts: dict[str, int] = {}
    for it in items:
        counts[it.meta["label"].title()] = counts.get(it.meta["label"].title(), 0) + 1
    facts = [{"label": k, "value": str(v)} for k, v in counts.items()]
    return cover_html(
        kind="daily", title=f"Resumen del día · {date_label}", emoji="🗞️", label="Resumen diario",
        source_type=None, facts=facts, hero=None, brand=brand, footer=brand,
    )


class CoverRenderer:
    """Mantiene un Chromium abierto para renderizar varias portadas seguidas."""

    def __enter__(self) -> "CoverRenderer":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        return self

    def render(self, html: str, dest: Path, full_page: bool = False, width: int = 1280) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._page.set_viewport_size({"width": width, "height": 720})
        tmp = dest.with_suffix(".html")
        tmp.write_text(html, encoding="utf-8")  # file:// para poder cargar fuentes e imágenes locales
        self._page.goto(tmp.resolve().as_uri(), wait_until="networkidle")
        self._page.evaluate("document.fonts.ready")
        self._page.screenshot(path=str(dest), type="png", full_page=full_page)
        tmp.unlink(missing_ok=True)
        return dest

    def __exit__(self, *exc: Any) -> None:
        self._browser.close()
        self._pw.stop()
