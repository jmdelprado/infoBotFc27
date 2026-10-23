# Feature Specification: Filtraciones por secciones y calendario solo oficial

**Feature Branch**: `003-oficial-calendario` | **Created**: 2026-10-23 | **Status**: Implemented

**Input**: "Mejorar la clasificación. En el calendario únicamente aparece lo oficial y los modos de juego; las filtraciones
se dividen entre los temas. El único canal para lo oficial es el calendario: cada vez que se actualice se muestra una
imagen de las dos semanas venideras con inicio y fin de eventos, evoluciones, etc. en vigor."

## User Scenarios & Testing

### US1 - Filtraciones por tipo (P1)
Toda filtración se publica en la sección de su tipo (Promos, Cartas, Objetivos, SBC, Evoluciones, Eventos).
La sección "Filtraciones" deja de usarse.

### US2 - Lo oficial solo en el calendario (P1)
Lo que ya está disponible en el juego o ha anunciado EA no se publica como mensaje: entra en el calendario.

### US3 - Calendario de 2 semanas (P1)
Cuando el contenido oficial cambia (o cambia el día), se publica una imagen nueva con los próximos 14 días, una barra
por elemento (inicio → fin) y la lista en texto; se fija y se borra la versión anterior.

### US4 - Modos de juego (P2)
Nuevo tipo "mode" (torneos, Rivals/Champions especiales, The Grounds, drafts…) que aparece en el calendario si es oficial.

## Requirements
- **FR-301**: Clasificación estricta: "official" solo si está disponible ya o lo ha anunciado EA; el resto es "leak".
- **FR-302**: `topic_for(kind, "official")` → ninguna sección; `topic_for(kind, "leak")` → sección del tipo.
- **FR-303**: `state["calendar"]` contiene solo entradas oficiales (tipo, nombre, inicio, fin, detalle) y caduca por fecha de fin.
- **FR-304**: El calendario muestra en vigor / próximos 14 días / más adelante; nunca muestra filtraciones.
- **FR-305**: El resumen diario incluye solo filtraciones.

## Success Criteria
- **SC-301**: 0 filtraciones en el calendario. **SC-302**: 0 mensajes sueltos de contenido oficial.
