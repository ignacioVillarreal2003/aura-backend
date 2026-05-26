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
| [overview.md](overview.md) | Prefijo `/api/v1`, CORS, métricas y dependencias típicas del servicio. |
| [authentication.md](authentication.md) | Bearer JWT, llamadas servicio-a-servicio y rutas públicas. |
| [endpoints.md](endpoints.md) | Referencia completa de todos los endpoints: campos, tipos, restricciones, enums y códigos de respuesta. |
| [documents.md](documents.md) | Resumen narrativo de los flujos de documentos (ingesta, consulta, descarga, borrado). |

La **fuente de verdad ejecutable** sigue siendo OpenAPI (`/api/openapi.json`) y Swagger (`/api/docs`); `endpoints.md` documenta los contratos con el detalle derivado del código fuente.
