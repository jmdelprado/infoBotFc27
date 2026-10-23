# Contrato: mensajes del canal

## Novedad (1 álbum + 1 texto)
1. **Álbum** (`sendMediaGroup`): portada generada + imágenes originales (máx. 10 en total).
   Caption de la portada: `<b>{emoji} {TÍTULO}</b>` + etiqueta Oficial/Filtración.
2. **Texto** (`sendMessage`, HTML), como respuesta al álbum:

```
{emoji} <b>{TIPO} · {título}</b>
{✅ OFICIAL | 🕵️ FILTRACIÓN}

{summary}

▸ <b>{label}</b>: {value}      (key_facts, uno por línea)

<blockquote expandable>{details}</blockquote>

#{Tipo} #{Oficial|Filtracion} #FC27
<a href="{url}">Fuente: @{cuenta}</a>   (opcional, discreto)
```

Si la novedad no tiene imágenes, solo se envía la portada con el texto completo como caption si cabe
(≤ 1024 caracteres); si no cabe, portada + texto aparte.

| kind | emoji | hashtag | color de la portada |
|---|---|---|---|
| promo | 🔥 | #Promo | naranja → rojo |
| card | 🃏 | #Carta | dorado |
| objective | 🎯 | #Objetivos | verde |
| sbc | 🧩 | #SBC | azul |
| event | 📢 | #Evento | morado |

## Mensaje fijado (se edita)
```
📌 <b>ESTADO ACTUAL · FC 27</b>   (actualizado dd/mm hh:mm)
🔥 Promo activa: …
🎯 Objetivos en vigor: • …
🧩 SBCs: • …
🃏 Últimas cartas: • 89 Mbappé (DC) — Promo
🕵️ Últimas filtraciones: • …
```

## Resumen diario
Portada "RESUMEN DEL DÍA" + texto agrupado por tipo con un elemento por línea.
