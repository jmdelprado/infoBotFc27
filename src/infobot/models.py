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
    "evolution": {"emoji": "🧬", "label": "EVOLUCIÓN", "tag": "Evolucion"},
    "event": {"emoji": "📢", "label": "EVENTO", "tag": "Evento"},
}

# Secciones (temas) del grupo de Telegram, en el orden en que se crean.
# icon_color: uno de los colores admitidos por createForumTopic.
TOPICS = {
    "promo": {"name": "🔥 Promos", "icon_color": 16478047},
    "card": {"name": "🃏 Cartas", "icon_color": 16766590},
    "objective": {"name": "🎯 Objetivos", "icon_color": 9367192},
    "sbc": {"name": "🧩 SBC", "icon_color": 7322096},
    "evolution": {"name": "🧬 Evoluciones", "icon_color": 13338331},
    "event": {"name": "📢 Eventos", "icon_color": 16749490},
    "leak": {"name": "🕵️ Filtraciones", "icon_color": 16766590},
    "calendar": {"name": "📅 Calendario", "icon_color": 7322096},
    "daily": {"name": "🗞️ Resumen diario", "icon_color": 9367192},
}


TOPIC_INTROS = {
    "promo": "Aquí aparecen las <b>promos y equipos</b> oficiales: cuándo salen, qué traen y hasta cuándo duran.",
    "card": "Aquí aparecen las <b>cartas nuevas</b> confirmadas: media, posición, club y promo.",
    "objective": "Aquí aparecen los <b>objetivos</b>: qué hay que hacer, la recompensa y la fecha de fin.",
    "sbc": "Aquí aparecen los <b>SBC</b>: requisitos, coste aproximado, recompensa y fecha de fin.",
    "evolution": "Aquí aparecen las <b>evoluciones</b>: requisitos para meter la carta, coste y mejoras.",
    "event": "Aquí aparecen los <b>eventos</b>: mantenimientos, TOTW, torneos, recompensas y otras noticias.",
    "leak": "Aquí aparecen las <b>filtraciones y rumores</b>. 🕵️ Nada de esto está confirmado por EA.",
    "calendar": "Aquí está el <b>calendario</b> con todo lo que hay para hacer y jugar, ordenado por fecha de fin. "
                "Se actualiza solo.",
    "daily": "Aquí aparece cada noche el <b>resumen del día</b> con todas las novedades.",
}


def topic_for(kind: str, source_type: str) -> str:
    """Sección de una novedad: las filtraciones van siempre a Filtraciones."""
    if source_type == "leak":
        return "leak"
    return kind if kind in TOPICS else "event"

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
        extra = {k: data[k] for k in ("promo", "cards", "objectives", "sbcs", "evolutions", "events") if data.get(k)}
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
