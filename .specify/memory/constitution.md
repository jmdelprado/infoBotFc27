# InfoBot Constitution

## Core Principles

### I. Coste cero (NO NEGOCIABLE)
Todo el sistema MUST funcionar sin pagar nada y sin depender de periodos de prueba:
- Sin APIs de pago (ni la API oficial de X ni la API de Anthropic con facturación por uso).
- Ejecución en GitHub Actions dentro de la cuota gratuita (repositorio privado, < 2000 min/mes).
- El análisis con IA usa Claude Code en modo no interactivo (`claude -p`) con la suscripción existente
  del propietario (`CLAUDE_CODE_OAUTH_TOKEN`).
Cualquier dependencia nueva MUST ser gratuita y de uso ilimitado o con una cuota gratuita permanente.

### II. Resúmenes autosuficientes
Cada publicación en Telegram MUST contener toda la información útil (texto completo, datos extraídos
e imágenes originales) para que el lector no tenga que abrir el tweet. El enlace al tweet es opcional
y secundario.

### III. Fidelidad y transparencia de la fuente
- El bot MUST NOT inventar datos: si un dato no aparece en el texto ni en la imagen, se omite.
- Toda novedad MUST etiquetarse como **Oficial** o **Filtración**, y en los mensajes van siempre separadas.
- Las cifras (media, precios, requisitos) se copian tal cual de la fuente.

### IV. Solo novedades, sin duplicados
Cada tweet se procesa una sola vez (se registra su identificador). El bot mantiene un estado actual de
FC 27 y solo publica lo nuevo o lo que ha cambiado. Una ejecución repetida sin tweets nuevos MUST
NOT publicar nada (salvo el resumen diario programado).

### V. Fuentes intercambiables y resiliencia
La lectura de X va detrás de una interfaz `Source`. Si una fuente falla, el sistema MUST intentar con la
alternativa, registrar el error y terminar sin romper el estado guardado. Un fallo de Telegram o de Claude
MUST NOT marcar los tweets como procesados.

### VI. Simplicidad
Python 3.12, pocas dependencias y SQLite + JSON como almacenamiento. Sin servidores ni bases de datos
externas. Se prefiere código pequeño y legible a abstracciones innecesarias (YAGNI).

## Restricciones adicionales

- **Idioma:** todos los mensajes del canal y la documentación, en español.
- **Secretos:** las cookies de X, el token de Claude y el token de Telegram solo viven en GitHub Secrets
  o en un `.env` local ignorado por git. Nunca en el código ni en los logs.
- **Cuentas:** el bot usa la cuenta secundaria de X `@infobotfc`, nunca la cuenta personal del propietario.
- **Estilo del canal:** plantilla homogénea (emoji por tipo, título en negrita, datos clave, bloque
  plegable, hashtags) y una portada generada para cada novedad.

## Flujo de desarrollo

- Desarrollo guiado por especificaciones con spec-kit: constitution → specify → plan → tasks → implement.
- La lógica sin red (clasificación, fusión de estado, formateo) MUST tener tests con pytest y datos
  de ejemplo guardados en `tests/fixtures/`.
- Antes de publicar en el canal real hay un modo `--dry-run`/`preview` que genera los mensajes en local.

## Governance

Esta constitución está por encima de cualquier otra práctica del proyecto. Las modificaciones se
documentan en este archivo, suben la versión (semver: MAJOR = eliminar o redefinir principios,
MINOR = añadir principios o secciones, PATCH = aclaraciones) y las aprueba el propietario. Cada plan y
cada lista de tareas de spec-kit MUST comprobar que cumple estos principios.

**Version**: 1.0.0 | **Ratified**: 2026-10-23 | **Last Amended**: 2026-10-23
