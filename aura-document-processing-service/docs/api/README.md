# Documentación de la API HTTP

Este directorio describe de forma general el **Aura Document Processing Service**: autenticación, visión del servicio y flujos principales de documentos (creación, ingesta, consulta y descarga).

La **fuente canónica** de contratos (esquemas de request/response, códigos y parámetros exactos) es la especificación **OpenAPI** expuesta por la propia aplicación en tiempo de ejecución.

## OpenAPI y exploración interactiva

Con el servicio en marcha (por defecto en el puerto configurado en `APP_PORT`, habitualmente `8000`):

| Recurso | Ruta |
|--------|------|
| Esquema OpenAPI (JSON) | `/api/openapi.json` |
| Swagger UI | `/api/docs` |
| ReDoc | `/api/redoc` |

Las rutas anteriores **no requieren autenticación** a nivel de middleware (están en la lista de exclusiones).

## Contenido de esta carpeta

| Archivo | Descripción |
|---------|-------------|
| [overview.md](overview.md) | Prefijo `/api`, CORS, métricas y dependencias típicas del servicio. |
| [authentication.md](authentication.md) | Bearer JWT, llamadas servicio-a-servicio y rutas públicas. |
| [documents.md](documents.md) | Creación/ingesta, consulta, descarga, borrados y post-procesado de documentos; mención breve de fragmentos. |

Para el detalle de cada endpoint, usar siempre **OpenAPI** o **Swagger/ReDoc**.
