# Errores y códigos de estado HTTP

## Formato general de error

Cuando el handler personalizado procesa una excepción de dominio (`ServiceException` y subclases) o adapta respuestas de DRF, el cliente recibe JSON con al menos:

```json
{
  "error": "<código_estable>",
  "detail": "<mensaje para humanos>",
  "status_code": <número HTTP>
}
```

- **`error`:** identificador estable para lógica en el cliente (p. ej. `insufficient_permissions`, `not_found`).
- **`detail`:** texto explicativo.
- **`status_code`:** repite el código HTTP del response.

### Validación (400)

Si DRF devuelve errores de validación de campos, el handler puede incluir **`fields`** con el detalle por campo además de `detail` genérico (“Validation failed”). El código `error` suele ser `bad_request`.

## Códigos `error` frecuentes (dominio)

Definidos en [core/exceptions/base.py](../core/exceptions/base.py) y usados por los servicios:

| `error` | HTTP | Significado típico |
|---------|------|----------------------|
| `not_found` | 404 | Recurso inexistente o no accesible en el contexto actual. |
| `validation_error` | 400 | Entrada inválida a nivel de dominio. |
| `forbidden` | 403 | prohibido por regla distinta a permisos (según caso). |
| `insufficient_permissions` | 403 | Falta alguno de los permisos requeridos en el token (`AccessControl.require_permissions`). |
| `conflict` | 409 | Conflicto de estado (p. ej. miembro duplicado). |
| `service_unavailable` | 503 | Dependencia externa no disponible. |
| `internal_error` | 500 | Situación no controlada (mensaje genérico al cliente). |

Otros códigos pueden aparecer según excepciones concretas de cada app (`error_code` en la excepción).

## HTTP status — guía rápida

| Status | Uso habitual en esta API |
|--------|---------------------------|
| **400** | Payload o query inválidos; validación DRF o de dominio. |
| **401** | No autenticado: falta credencial o token inválido (salvo rutas públicas). |
| **403** | Autenticado pero sin permiso suficiente (`insufficient_permissions` u otra regla `ForbiddenException`). |
| **404** | Chat, mensaje o miembro no encontrado en el alcance del usuario. |
| **409** | Conflicto (recurso duplicado o estado incompatible). |
| **429** | Throttling excedido. |
| **502** | Bad gateway hacia un servicio dependiente (p. ej. LLM) cuando está modelado así. |
| **503** | Servicio o dependencia temporalmente no disponible. |
| **500** | Error interno no manejado como `ServiceException`. |

## Health check

- **`GET /api/v1/health`:** **`200`** si todas las comprobaciones reportan `ok`; **`503`** con `"status": "degraded"` si alguna dependencia (p. ej. base de datos o Redis) falla.

## Documentación de códigos en OpenAPI

El esquema generado documenta respuestas de error comunes por endpoint (`standard_error_responses` en código). Para el detalle exacto por operación, consultar **`GET /api/schema/`**.
