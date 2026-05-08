# Visión general de la API — Aura Document Collection Service

Servicio Django REST Framework (DRF) que expone colecciones de documentos, niveles de clasificación MAC, compartimientos y autorizaciones de usuario (clearance y compartimentos). Está pensado para integrarse con un **servicio de autenticación** externo y con llamadas **service-to-service** mediante API key.

Para una lectura **solo de dominio** (roles, tablas y flujos típicos, sin centrarse en rutas HTTP), ver [vision-general-api-y-datos.md](vision-general-api-y-datos.md).

## Prefijo de la API REST

Los recursos de negocio viven bajo **`/api/v1/`** (salvo rutas especiales indicadas más abajo).

## Formato y cabeceras

- **Formato**: JSON únicamente (`Content-Type: application/json` en escrituras).
- **Autenticación**: ver [permissions.md](permissions.md).
- **Trazabilidad**: el servidor propaga **`X-Correlation-Id`**. Puedes enviarlo en la petición; si no llega, se genera uno. La respuesta devuelve el mismo valor en esa cabecera.

## Contrato público complementario

Además de esta documentación, el proyecto incluye OpenAPI generado con **drf-spectacular**:

| Ruta            | Descripción                    |
|-----------------|--------------------------------|
| `/api/schema/`  | Esquema OpenAPI (JSON/YAML)     |
| `/api/docs/`    | Swagger UI                     |
| `/api/redoc/`   | ReDoc                          |

Las rutas de esquema y documentación **no exigen credenciales** (están excluidas del middleware de autenticación).

## Operaciones públicas sin credenciales

| Método | Ruta               | Propósito        |
|--------|-------------------|------------------|
| `GET`  | `/api/v1/health`  | Comprobación de vida |

Respuesta ejemplo: `{ "status": "ok" }`.

## Observabilidad y administración

- **Métricas Prometheus**: expuestas en **`/metrics`** (sin pasar por el flujo Bearer del middleware de auth en rutas típicas de `django_prometheus`; coherente con la exclusión configurada si aplica).
- **Panel Django Admin**: bajo **`/admin/`** (uso operativo habitual, fuera del alcance de la API JSON documentada aquí).

## Paginación (listados)

Las respuestas paginadas siguen el estilo **`PageNumberPagination`** de DRF:

- **`page`**: número de página (query).
- **`page_size`**: tamaño (opcional; por defecto **20**, máximo **100**).
- Cuerpo: objeto con típicamente `count`, `next`, `previous`, `results` (lista de elementos).

Los conjuntos ordenables exponen **`ordering`** (campos admitidos están detallados en [endpoints.md](endpoints.md)).

## Convenciones de identificadores

Los IDs enteros en path deben ser **positivos** (regex del servicio: no se admite `"0"`).

## Errores

El cuerpo de error unificado y los códigos HTTP se documentan en [errors-and-status-codes.md](errors-and-status-codes.md).

## Permisos de aplicación

Los permisos requeridos por operación se listan en [permissions.md](permissions.md).

## Límites de tasa (throttling)

DRF aplica *throttling* anon + usuario. Valores por defecto en desarrollo/base: **30/min** (anon) y **120/min** (usuario); en producción suelen reducirse vía configuración (`THROTTLE_ANON_RATE`, `THROTTLE_USER_RATE`). Una petición rechazada responde **HTTP 429** (ver errores).

## CORS

Los orígenes permitidos dependen de `CORS_ORIGINS` en configuración (o lista local por defecto si está vacío en desarrollo). `CORS_ALLOW_CREDENTIALS` está habilitado.
