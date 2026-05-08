# Documentación — Aura Chat Service

Documentación orientada a integradores y al equipo de producto. Complementa el **contrato automático** OpenAPI del servicio.

| Documento | Contenido |
|-----------|-----------|
| [api-summary.md](api-summary.md) | Visión de producto: propósito del servicio, conceptos, tablas, flujos típicos y límites de responsabilidad. |
| [api-overview.md](api-overview.md) | Versión de la API, autenticación, formato de errores, paginación, rutas públicas y enlaces al esquema en vivo. |
| [endpoints.md](endpoints.md) | Catálogo de rutas HTTP: método, path, permiso requerido, qué hace el endpoint y para qué se usa. |
| [permissions.md](permissions.md) | Referencia de constantes de permiso y ámbito funcional. |
| [errors-and-status-codes.md](errors-and-status-codes.md) | Formato de respuestas de error y códigos HTTP habituales. |
| [websockets.md](websockets.md) | Conexión WebSocket al chat (URL, auth, cierres y tipos de mensaje). |

## Esquema OpenAPI (generado)

En un entorno donde el servicio está levantado:

- **JSON Schema:** `GET /api/schema/`
- **Swagger UI:** `GET /api/docs/`
- **ReDoc:** `GET /api/redoc/`

Los tipos de request/response exactos y los parámetros de query viven ahí; esta carpeta describe el **comportamiento** y los **permisos** en lenguaje natural.
