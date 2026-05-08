# Errores y códigos de estado — Aura Document Collection Service

## Formato JSON de error (API de negocio)

Para la mayoría de fallos devueltos por vistas DRF y por excepciones de dominio (`ServiceException`), el cuerpo sigue esta forma:

```json
{
  "error": "codigo_maquina",
  "detail": "Mensaje legible o estructura de validación",
  "status_code": 400
}
```

- **`error`**: código estable para lógica de cliente (puede coincidir con el `error_code` de excepciones de servicio).
- **`detail`**: mensaje humano o, en validaciones DRF, el payload de errores de campo tras el mapeo del *exception handler*.
- **`status_code`**: repetición numérica del HTTP por conveniencia.

Referencia OpenAPI interna: `ApiErrorBody` en `core/openapi/common.py`.

## Respuestas del middleware de autenticación

Cuando falla la autenticación **antes** de llegar al view (token ausente, cabeceras de servicio incorrectas, etc.), la respuesta también usa típicamente `error`, `detail` y `status_code`, pero **`detail`** puede ser un string fijo documentado por caso (no siempre el mismo formato que las validaciones DRF).

Cabeceras notables:

- Respuestas **401** por Bearer suelen incluir **`WWW-Authenticate: Bearer`**.

---

## Códigos HTTP por categoría

| Código | Significado habitual en este servicio |
|--------|---------------------------------------|
| **200** | Éxito en lecturas y actualizaciones que devuelven cuerpo. |
| **201** | Recurso creado. |
| **204** | Éxito sin cuerpo (p. ej. `DELETE`). |
| **400** | Entrada inválida (validación de serializer, cabeceras S2S mal formadas, etc.). |
| **401** | No autenticado: falta Bearer, token inválido/expirado, clave de servicio ausente/errónea en contextos que devuelven 401. |
| **403** | Autenticado pero prohibido (permisos de aplicación insuficientes, o clave de servicio inválida donde se usa 403). |
| **404** | Recurso de dominio no encontrado; en algunos flujos de auth middleware, usuario no encontrado para el token (**404** según configuración actual). |
| **405** | Método HTTP no permitido en la ruta. |
| **409** | Conflicto de unicidad/asociación (enlace duplicado, nivel o compartimento duplicado, etc.). |
| **429** | Límite de peticiones (*throttle*). |
| **500** | Error interno no manejado o fallo genérico de autenticación inesperado en middleware. |
| **503** | Dependencia caída o no disponible (p. ej. servicio de autenticación inalcanzable). |

---

## Códigos `error` del middleware de autenticación (Bearer y S2S)

| `error` | HTTP | Contexto breve |
|---------|------|----------------|
| `missing_token` | 401 | Ruta protegida sin Bearer. |
| `invalid_token` | 401 | Token rechazado o respuesta inválida del proveedor. |
| `unauthorized` | 403 | El proveedor de auth denegó el acceso (403 upstream). |
| `user_not_found` | 404 | Usuario inexistente según proveedor (404 upstream). |
| `service_unavailable` | 503 | Timeout/red/5xx hacia el proveedor. |
| `authentication_error` | 500 | Error de proveedor no clasificado. |
| `internal_error` | 500 | Excepción inesperada en el middleware de auth. |
| `missing_service_key` | 401 | `X-Service-Api-Key` vacío cuando se intenta S2S. |
| `invalid_service_key` | 403 | API key no coincide con `SERVICE_API_KEY`. |
| `missing_user_id` | 400 | Falta `X-User-Id`. |
| `invalid_user_id` | 400 | `X-User-Id` no es entero. |
| `missing_user_email` | 400 | Falta `X-User-Email`. |

---

## Códigos `error` de negocio (excepciones de dominio)

Definidas en `core/domain/document_collection_exceptions.py` y mapeadas vía `ServiceException`:

| `error` | HTTP | Descripción |
|---------|------|-------------|
| `document_collection_not_found` | 404 | Colección inexistente o no activa. |
| `document_link_not_found` | 404 | Enlace documento–colección no encontrado. |
| `document_not_available` | 404 | Documento inexistente o eliminado. |
| `duplicate_document_link` | 409 | El documento ya está enlazado a la colección. |
| `classification_level_not_found` | 404 | Nivel de clasificación no encontrado. |
| `duplicate_classification_level` | 409 | Nombre o rango duplicado. |
| `classification_level_in_use` | 409 | No se puede borrar: está en uso. |
| `compartment_not_found` | 404 | Compartimento no encontrado. |
| `duplicate_compartment` | 409 | Nombre de compartimento duplicado. |
| `compartment_in_use` | 409 | No se puede borrar: está en uso. |
| `user_clearance_not_found` | 404 | No hay clearance para el usuario. |
| `duplicate_user_compartment` | 409 | El usuario ya tiene ese compartimento. |
| `user_compartment_not_found` | 404 | Asignación usuario–compartimento no existe. |

## Permisos insuficientes

| `error` | HTTP | Descripción |
|---------|------|-------------|
| `insufficient_permissions` | 403 | El usuario autenticado no incluye el permiso de aplicación requerido. |

## Errores genéricos del *exception handler*

Cuando DRF maneja excepciones estándar, el handler envuelve la respuesta y asigna un `error` genérico según el status:

| HTTP | `error` por defecto |
|------|---------------------|
| 400 | `bad_request` |
| 401 | `unauthorized` |
| 403 | `forbidden` |
| 404 | `not_found` |
| 405 | `method_not_allowed` |
| 409 | `conflict` |
| 429 | `throttled` |
| 503 | `service_unavailable` |
| otro | `error` |

Errores no capturados por DRF → **500** con `error: "internal_error"`.

---

## Validación (`400`)

Los serializers pueden devolver en `detail` la estructura típica de DRF (`{ "campo": ["mensaje"] }` o `non_field_errors`) después del formateo unificado — trata `detail` como **mensaje legible y/o árbol de errores**.

## Referencia rápida OpenAPI (`standard_error_responses`)

Las descripciones de esquema alineadas con la API incluyen mensajes cortos para: **400** (validación), **401** (credenciales), **403** (sin permiso de aplicación), **404** (no encontrado), **409** (conflicto), **503** (dependencia no disponible).
