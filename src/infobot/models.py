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
    "evocal": {"name": "📆 Calendario de evoluciones", "icon_color": 13338331},
    "daily": {"name": "🗞️ Resumen diario", "icon_color": 9367192},
}


TOPIC_INTROS = {
    "promo": "🔥 Aquí está cada <b>promo y equipo</b> en un único mensaje: fechas, equipos y todas sus cartas. "
             "Cuando hay novedades, el mensaje se vuelve a publicar completo abajo.",
    "card": "🃏 Aquí están las <b>cartas sueltas</b> (mejoras, cartas de jugador, recompensas): media, posición y club.",
    "objective": "🎯 Aquí están los <b>objetivos</b>: qué hay que hacer y sus recompensas.",
    "sbc": "🧩 Aquí están los <b>SBC</b>: requisitos, coste y recompensa.",
    "evolution": "🧬 Aquí están las <b>evoluciones</b>: requisitos, coste y mejoras.",
    "event": "📢 Aquí está <b>todo lo demás</b>: modos de juego, tienda, galería, mantenimientos…",
    "calendar": "✅ Aquí está el <b>calendario OFICIAL</b>: todo lo que ya está en el juego o ha confirmado EA, "
                "con su inicio y su fin en las próximas dos semanas. Se actualiza solo.",
    "evocal": "✅ Aquí está el <b>calendario de evoluciones</b>: todas las evoluciones activas de los próximos 30 días "
              "con su plazo y cuándo terminan. ⭐ <b>VIP</b> = pase premium. Datos oficiales del juego vía FUT.GG.",
    "daily": "🗞️ Aquí aparece cada noche el <b>resumen del día</b>: todo lo que ha cambiado en las últimas 24 horas.",
}


def topic_for(kind: str) -> str:
    """Sección de una ficha: la de su tipo (Promos, Cartas, Objetivos, SBC, Evoluciones); el resto, Eventos."""
    return kind if kind in TOPICS and kind not in ("calendar", "evocal", "daily") else "event"


# Etiqueta de cada ficha. "none" = sin etiqueta: las fuentes son fiables y se da por hecho.
SOURCE_TYPES = {
    "official": {"emoji": "✅", "label": "OFICIAL", "tag": "Oficial"},
    "prediction": {"emoji": "🔮", "label": "PREDICCIÓN", "tag": "Prediccion"},
    "none": {"emoji": "", "label": "", "tag": ""},
}


def normalize_source(value: str | None) -> str:
    """Las antiguas "leak" (filtración) pasan a "none"."""
    return value if value in SOURCE_TYPES else "none"


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
    story_id: int | None = None  # ficha a la que pertenece (en las fichas, su propio id)
    accounts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    @property
    def meta(self) -> dict[str, str]:
        return KINDS.get(self.kind, KINDS["event"])

    @property
    def source_meta(self) -> dict[str, str]:
        return SOURCE_TYPES[normalize_source(self.source_type)]

    @classmethod
    def from_analysis(cls, data: dict[str, Any]) -> "Item":
        extra = {k: data[k] for k in ("promo", "cards", "objectives", "sbcs", "evolutions", "events", "modes",
                                       "starts", "ends") if data.get(k)}
        return cls(
            kind=data["kind"],
            source_type=normalize_source(data["source_type"]),
            title=data["title"].strip(),
            summary=data["summary"].strip(),
            details=data.get("details", "").strip(),
            key_facts=data.get("key_facts", []),
            tweet_ids=[str(t) for t in data["tweet_ids"]],
            images=data.get("images", []),
            extra=extra,
            story_id=int(data.get("story_id") or 0) or None,
        )
