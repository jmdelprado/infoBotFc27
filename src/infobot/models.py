"""Modelos de datos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

KINDS = {
    "promo": {"emoji": "🔥", "label": "PROMO", "tag": "Promo"},
    "card": {"emoji": "🃏", "label": "CARTA NUEVA", "tag": "Carta"},
    "objective": {"emoji": "🎯", "label": "OBJETIVOS", "tag": "Objetivos"},
    "sbc": {"emoji": "🧩", "label": "SBC", "tag": "SBC"},
    "event": {"emoji": "📢", "label": "EVENTO", "tag": "Evento"},
}

SOURCE_TYPES = {
    "official": {"emoji": "✅", "label": "OFICIAL", "tag": "Oficial"},
    "leak": {"emoji": "🕵️", "label": "FILTRACIÓN", "tag": "Filtracion"},
}


@dataclass
class Tweet:
    id: str
    account: str
    created_at: datetime
    text: str
    url: str
    media: list[str] = field(default_factory=list)  # URLs remotas
    local_media: list[str] = field(default_factory=list)  # rutas locales tras descargar


@dataclass
class Item:
    """Una novedad lista para publicar."""

    kind: str
    source_type: str
    title: str
    summary: str
    details: str
    key_facts: list[dict[str, str]]
    tweet_ids: list[str]
    images: list[str]
    extra: dict[str, Any] = field(default_factory=dict)  # promo, cards, objectives, sbcs
    id: int | None = None
    accounts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    @property
    def meta(self) -> dict[str, str]:
        return KINDS.get(self.kind, KINDS["event"])

    @property
    def source_meta(self) -> dict[str, str]:
        return SOURCE_TYPES.get(self.source_type, SOURCE_TYPES["leak"])

    @classmethod
    def from_analysis(cls, data: dict[str, Any]) -> "Item":
        extra = {k: data[k] for k in ("promo", "cards", "objectives", "sbcs") if data.get(k)}
        return cls(
            kind=data["kind"],
            source_type=data["source_type"],
            title=data["title"].strip(),
            summary=data["summary"].strip(),
            details=data.get("details", "").strip(),
            key_facts=data.get("key_facts", []),
            tweet_ids=[str(t) for t in data["tweet_ids"]],
            images=data.get("images", []),
            extra=extra,
        )
