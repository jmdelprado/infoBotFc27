# Feature Specification: Resumen de novedades de FC 27 en Telegram

**Feature Branch**: `001-fc27-telegram-digest`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Un bot que lea publicaciones de ciertas cuentas de X/Twitter sobre EA SPORTS FC 27
(Ultimate Team), las analice y resuma, y vaya actualizando la información de objetivos, equipos/promos,
cartas nuevas, SBCs, etc. Publica en un canal de Telegram público y bonito, cada 4 horas, de forma
totalmente gratuita y sin depender del PC del propietario. Cuentas iniciales: @JuniorSintress y @FutPoliceLeaks."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recibir las novedades de FC 27 en el canal (Priority: P1)

Un seguidor del canal recibe, sin hacer nada, un mensaje por cada novedad relevante publicada por las cuentas
seguidas: título claro, tipo de novedad, datos clave, texto completo y las imágenes originales. Lo entiende
todo sin abrir X.

**Why this priority**: Es el valor central del producto. Sin esto no hay bot.

**Independent Test**: Con dos tweets de ejemplo (una promo y una carta filtrada) se ejecuta el ciclo y en el
canal aparecen dos mensajes con imágenes, tipo correcto y datos extraídos.

**Acceptance Scenarios**:

1. **Given** una cuenta seguida publica un tweet con una imagen de carta nueva, **When** se ejecuta el ciclo,
   **Then** el canal recibe un mensaje con la imagen, el nombre del jugador, la media, la posición y la etiqueta
   Filtración u Oficial.
2. **Given** un tweet sin relación con FC 27 (p. ej., un mensaje personal), **When** se ejecuta el ciclo,
   **Then** no se publica nada.
3. **Given** un tweet ya publicado en una ejecución anterior, **When** se ejecuta otra vez, **Then** no se repite.

---

### User Story 2 - Estado actual siempre a la vista (Priority: P2)

El seguidor abre el canal y, en el mensaje fijado, ve el estado actual de FC 27: promo activa y fechas,
objetivos en vigor, SBCs destacados y últimas filtraciones. Se actualiza solo cuando algo cambia.

**Why this priority**: Aporta una visión de conjunto, pero depende de la US1.

**Independent Test**: Tras procesar una promo nueva, el mensaje fijado se edita y muestra la promo como activa.

**Acceptance Scenarios**:

1. **Given** el estado indica la promo A activa, **When** llega una novedad oficial de la promo B,
   **Then** el mensaje fijado pasa a mostrar la promo B como activa.
2. **Given** un objetivo con fecha de fin pasada, **When** se ejecuta el ciclo, **Then** desaparece de "en vigor".

---

### User Story 3 - Canal con estilo propio (Priority: P2)

Cada novedad lleva como primera imagen una portada generada con estilo FC (tipo, título y datos clave).
Los mensajes siguen una plantilla homogénea con emojis, negritas, bloque plegable y hashtags para filtrar.

**Why this priority**: El usuario lo pidió expresamente para que el canal se vea bonito y atraiga seguidores.

**Independent Test**: El comando de vista previa genera las portadas PNG y los textos de un tweet de ejemplo
sin publicar nada.

**Acceptance Scenarios**:

1. **Given** una novedad de tipo SBC, **When** se publica, **Then** el álbum empieza con una portada 🧩 SBC
   y el texto lleva `#SBC`.

---

### User Story 4 - Resumen diario (Priority: P3)

Una vez al día el canal publica un resumen de lo ocurrido en las últimas 24 horas con su propia portada.

**Why this priority**: Es un extra útil para quien no mira el canal a menudo.

**Independent Test**: Con varias novedades guardadas, el modo diario genera un único mensaje con todas ellas.

**Acceptance Scenarios**:

1. **Given** cinco novedades en las últimas 24 h, **When** se lanza el resumen diario, **Then** se publica un
   solo mensaje que las agrupa por tipo.
2. **Given** ninguna novedad en 24 h, **When** se lanza el resumen diario, **Then** no se publica nada.

---

### Edge Cases

- La lectura de X falla (sesión caducada, bloqueo, límite de peticiones): se intenta con la fuente alternativa;
  si también falla, el ciclo termina sin perder estado y avisa en el log (y por Telegram al propietario si está configurado).
- Claude no responde o devuelve un JSON inválido: el tweet no se marca como procesado y se reintenta en el siguiente ciclo
  (como máximo 3 veces; después se descarta y se registra).
- Hilo de varios tweets o retuit: los retuits de cuentas no seguidas se tratan igual que el resto; las respuestas en
  hilo se agrupan con el tweet original si llegan en el mismo ciclo.
- Tweet con vídeo: se envía la miniatura del vídeo como imagen.
- Texto que supera el límite de Telegram: se divide en varios mensajes.
- Muchas novedades a la vez (p. ej., lanzamiento de promo con 20 tweets): se agrupan las del mismo tema en un solo
  mensaje y se respetan los límites de envío de Telegram.
- Primera ejecución: solo se procesan los tweets de las últimas 24 h para no inundar el canal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST leer los tweets nuevos (texto e imágenes) de una lista configurable de cuentas de X.
- **FR-002**: El sistema MUST ejecutarse automáticamente cada 4 horas sin depender del ordenador del propietario.
- **FR-003**: El sistema MUST clasificar cada tweet en: Promo/Equipo, Carta nueva, Objetivos, SBC, Evento/Noticia
  o Irrelevante, y marcarlo como Oficial o Filtración.
- **FR-004**: El sistema MUST extraer los datos estructurados disponibles (jugador, media, posición, club, liga,
  nación, nombre de la promo, fechas, requisitos, recompensas) leyendo el texto y las imágenes.
- **FR-005**: El sistema MUST NOT inventar datos que no aparezcan en la fuente.
- **FR-006**: El sistema MUST publicar cada novedad relevante en un canal público de Telegram, con el texto en español,
  las imágenes originales y una portada generada.
- **FR-007**: El sistema MUST mantener y mostrar en un mensaje fijado el estado actual (promo activa, objetivos en vigor,
  SBCs activos, últimas filtraciones), editándolo cuando cambie.
- **FR-008**: El sistema MUST procesar cada tweet una sola vez y no repetir publicaciones.
- **FR-009**: El sistema MUST publicar un resumen diario de las últimas 24 horas, si hay novedades.
- **FR-010**: El sistema MUST ofrecer un modo de vista previa que genere los mensajes y las portadas en local sin publicar.
- **FR-011**: El sistema MUST funcionar sin coste económico (ver Constitución, Principio I).
- **FR-012**: El sistema MUST guardar los secretos (sesión de X, token de Claude, token de Telegram) fuera del código.
- **FR-013**: Añadir o quitar una cuenta seguida MUST requerir solo editar un archivo de configuración.

### Key Entities

- **Tweet**: id, cuenta, fecha, texto, imágenes, enlace, estado de procesamiento (pendiente, procesado, descartado, intentos).
- **Novedad (Item)**: tipo, oficial o filtración, título, datos estructurados, resumen en español, imágenes, tweets de origen.
- **Estado actual**: promo activa, objetivos en vigor, SBCs activos, últimas filtraciones, fecha de actualización.
- **Publicación**: id del mensaje de Telegram, novedad asociada y fecha de envío (para no repetir y para editar el fijado).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una novedad aparece en el canal, como mucho, 4 horas y 15 minutos después de publicarse en X.
- **SC-002**: 0 publicaciones duplicadas en 7 días de funcionamiento.
- **SC-003**: Al menos 9 de cada 10 novedades se clasifican con el tipo correcto (revisión manual de una muestra).
- **SC-004**: 0 € de coste mensual.
- **SC-005**: Un seguidor entiende la novedad sin abrir X en el 100 % de los mensajes (todas llevan texto e imágenes).
- **SC-006**: Si falla una ejecución, la siguiente se recupera sola y publica lo pendiente.

## Assumptions

- El propietario tiene una suscripción de Claude que permite usar Claude Code en modo no interactivo y acepta que el bot
  consuma parte de su cuota.
- La cuenta secundaria `@infobotfc` sigue o puede ver públicamente las cuentas objetivo.
- Las cuentas seguidas publican mayoritariamente en inglés o en español; los mensajes del canal siempre salen en español.
- El canal de Telegram es público y el bot es su administrador.
- Leer X sin la API oficial puede dejar de funcionar por cambios de X; se acepta este riesgo a cambio del coste cero.
- Fuera de alcance en la v1: página web, comandos interactivos del bot, varios idiomas.
