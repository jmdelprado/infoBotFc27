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
    "mode": {"emoji": "🎮", "label": "MODO DE JUEGO", "tag": "ModoDeJuego"},
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
    "calendar": {"name": "📅 Calendario", "icon_color": 7322096},
    "daily": {"name": "🗞️ Resumen diario", "icon_color": 9367192},
}


TOPIC_INTROS = {
    "promo": "🕵️ Aquí aparecen las <b>filtraciones de promos y equipos</b>: qué se espera, cuándo y con qué cartas.",
    "card": "🕵️ Aquí aparecen las <b>cartas filtradas</b>: media, posición, club y promo antes de que salgan.",
    "objective": "🕵️ Aquí aparecen los <b>objetivos filtrados</b>: qué habrá que hacer y sus recompensas.",
    "sbc": "🕵️ Aquí aparecen los <b>SBC filtrados</b>: requisitos, coste estimado y recompensa.",
    "evolution": "🕵️ Aquí aparecen las <b>evoluciones filtradas</b>: requisitos, coste y mejoras.",
    "event": "🕵️ Aquí aparecen otras <b>filtraciones y rumores</b>: modos, eventos, tienda, TOTW…",
    "calendar": "✅ Aquí está el <b>calendario OFICIAL</b>: todo lo que ya está en el juego o ha confirmado EA, "
                "con su inicio y su fin en las próximas dos semanas. Se actualiza solo.",
    "daily": "Aquí aparece cada noche el <b>resumen del día</b> con todas las filtraciones.",
}


def topic_for(kind: str, source_type: str) -> str | None:
    """Sección de una novedad.

    - Filtraciones: a la sección de su tipo (Promos, Cartas, Objetivos, SBC, Evoluciones, Eventos).
    - Oficial: None → no se publica como mensaje; solo alimenta el Calendario.
    """
    if source_type == "official":
        return None
    return kind if kind in TOPICS and kind not in ("calendar", "daily") else "event"

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
        extra = {k: data[k] for k in ("promo", "cards", "objectives", "sbcs", "evolutions", "events", "modes",
                                       "starts", "ends") if data.get(k)}
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
