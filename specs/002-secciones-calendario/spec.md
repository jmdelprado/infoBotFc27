# Feature Specification: Secciones (temas) y calendario

**Feature Branch**: `002-secciones-calendario`

**Created**: 2026-10-23

**Status**: Draft

**Input**: "Publicar en un grupo de Telegram con Temas en lugar de un canal, con una sección por tipo
(incluida una nueva sección de Evoluciones) y una sección Calendario donde se vea todo lo que hay para hacer o jugar."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Novedades por secciones (Priority: P1)
El seguidor entra en el grupo y elige una sección (Promos, Cartas, Objetivos, SBC, Evoluciones, Eventos,
Filtraciones, Resumen diario). Cada novedad aparece solo en la sección que le corresponde.

**Independent Test**: Con los tweets de ejemplo, una promo filtrada va a Filtraciones, un SBC oficial a SBC y unos objetivos oficiales a Objetivos.

**Acceptance Scenarios**:
1. **Given** una novedad oficial de tipo SBC, **When** se publica, **Then** aparece en la sección 🧩 SBC.
2. **Given** una novedad de cualquier tipo marcada como filtración, **When** se publica, **Then** aparece en 🕵️ Filtraciones.
3. **Given** el grupo sin secciones creadas, **When** se ejecuta el bot por primera vez, **Then** crea las secciones él solo y recuerda sus identificadores.

### User Story 2 - Evoluciones (Priority: P1)
Las evoluciones (mejoras de cartas con requisitos, coste y niveles) se detectan como un tipo propio, con sus requisitos, coste, mejoras y fecha de fin.

### User Story 3 - Calendario (Priority: P1)
En la sección 📅 Calendario hay siempre un calendario actualizado con todo lo que está activo o por llegar
(promos, objetivos, SBCs, evoluciones, eventos), ordenado por fecha de fin: "Termina hoy", "Termina mañana",
"Esta semana", "Más adelante" y "Próximamente". Se muestra como imagen y como texto, y se edita en lugar de repetirse.

**Acceptance Scenarios**:
1. **Given** un SBC que termina mañana, **When** se actualiza el calendario, **Then** aparece en "Termina mañana".
2. **Given** un objetivo ya caducado, **When** se actualiza, **Then** desaparece.
3. **Given** un evento con fecha de inicio futura, **When** se actualiza, **Then** aparece en "Próximamente".

### Edge Cases
- Elementos sin fecha de fin: van a "Sin fecha confirmada".
- Alguien borra una sección: el bot la vuelve a crear en la siguiente ejecución.
- El mensaje del calendario se borra: se crea de nuevo y se fija.

## Requirements *(mandatory)*
- **FR-101**: El sistema MUST publicar en un grupo con Temas, una sección por tipo, además de General, Filtraciones, Resumen diario y Calendario.
- **FR-102**: Las filtraciones MUST ir a la sección Filtraciones, sea cual sea su tipo.
- **FR-103**: El sistema MUST reconocer el tipo "evolución" y extraer sus requisitos, coste, mejoras y fecha de fin.
- **FR-104**: El sistema MUST mantener un calendario (imagen + texto) en la sección Calendario, editándolo cuando cambie.
- **FR-105**: El estado actual sigue fijado en General.
- **FR-106**: Las secciones se crean automáticamente si no existen.

## Success Criteria *(mandatory)*
- **SC-101**: El 100 % de las novedades se publican en la sección correcta.
- **SC-102**: El calendario nunca muestra elementos caducados en el momento de su actualización.

## Assumptions
- El propietario crea el grupo, activa Temas y hace administrador al bot con el permiso de gestionar temas.
- Los miembros no pueden escribir (lo configura el propietario en los permisos del grupo).
