# Autenticación, autorización y errores

Implementación: `core/authentication/` · `core/authorization/` · `core/exceptions/`

---

## Los tres métodos de autenticación

### 1. JWT de usuario — `Authorization: Bearer <token>`

Para llamadas directas del frontend o cualquier cliente que tenga un token del usuario.

```http
GET /api/v1/notifications/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiJ9...
```

El middleware llama a `AUTHENTICATION_SERVICE_URL/auth/validate` con el token. La respuesta del auth service debe incluir:

| Campo | Tipo | Descripción |
| ----- | ---- | ----------- |
| `id` o `user_id` | entero | ID del usuario |
| `email` | string | Email |
| `username` | string | Nombre de usuario |
| `roles` | lista de strings | Roles del usuario |
| `permissions` | lista de strings | Permisos individuales (p. ej. `NOTIFICATION_INBOX_LIST`) |
| `is_super_admin` | booleano | Si es super admin |

El resultado se cachea en Redis durante `AUTH_TOKEN_CACHE_TTL_SECONDS` (por defecto 60 s) para evitar un round-trip al auth service en cada request.

---

### 2. Service key con usuario — `X-Service-Api-Key`

Para microservicios que ya validaron al usuario y reenvían la petición en su nombre (p. ej. un API gateway).

```http
GET /api/v1/notifications/ HTTP/1.1
X-Service-Api-Key: <SERVICE_API_KEY>
X-User-Id: 42
X-User-Email: usuario@ejemplo.com
X-User-Roles: user,premium
X-User-Permissions: NOTIFICATION_INBOX_LIST,NOTIFICATION_UNREAD_COUNT_GET
```

Cabeceras requeridas y opcionales:

| Cabecera | Requerida | Descripción |
| -------- | --------- | ----------- |
| `X-Service-Api-Key` | Sí | Debe coincidir con `SERVICE_API_KEY` (comparación en tiempo constante) |
| `X-User-Id` | Sí | ID del usuario suplantado (entero positivo) |
| `X-User-Email` | Sí | Email del usuario |
| `X-User-Roles` | No | Roles separados por coma |
| `X-User-Permissions` | No | Permisos separados por coma |

Si la clave existe pero no coincide → **403**. Si la clave está presente pero `X-User-Id` o `X-User-Email` faltan → **400**.

---

### 3. Token interno — `X-Internal-Token`

Exclusivamente para `POST /api/v1/internal/events/`. Las rutas bajo `/api/v1/internal/*` están excluidas del JWT en `AUTHENTICATION_EXCLUDED_PATHS`, pero cada vista valida este token manualmente con `hmac.compare_digest` para evitar timing attacks.

```http
POST /api/v1/internal/events/ HTTP/1.1
Content-Type: application/json
X-Internal-Token: <NOTIFICATION_INTERNAL_API_TOKEN>
```

Si el token falta o no coincide → **401** con `{"detail": "Unauthorized internal call.", "error": "unauthorized"}`.

---

## Rutas excluidas del JWT

Las siguientes rutas no pasan por validación de token ni de service key (definidas en `AUTHENTICATION_EXCLUDED_PATHS`):

| Patrón | Notas |
| ------- | ----- |
| `/api/v1/health` | Health check |
| `/metrics` | Prometheus |
| `/admin/*` | Django admin |
| `/api/schema*` | OpenAPI schema |
| `/api/docs*` | Swagger UI |
| `/api/redoc*` | ReDoc |
| `/api/v1/internal/*` | Protegidas por `X-Internal-Token` en la vista |
| `/api/v1/event-types/` | Catálogo público |

Las peticiones `OPTIONS` siempre pasan sin validación (preflight CORS).

---

## Autorización por permiso

Las vistas de bandeja, preferencias y SSE verifican permisos explícitamente vía `AccessControl.require_permissions`. Los permisos se definen como strings en `core/authorization/permissions.py` y el auth service los incluye en el JWT.

Un usuario con el permiso especial `"*"` en su lista supera cualquier verificación de permisos (útil para service accounts internos).

Si faltan permisos → **403** con `error_code: insufficient_permissions`.

---

## Formato de errores

Todos los errores siguen el mismo shape (manejador global en `core/exceptions/handler.py`):

```json
{
  "error": "not_found",
  "detail": "Notification not found.",
  "status_code": 404
}
```

En errores de validación de campos el body incluye además `"fields"`:

```json
{
  "error": "bad_request",
  "detail": "Validation failed",
  "status_code": 400,
  "fields": {
    "status": ["\"invalido\" is not a valid choice."]
  }
}
```

Códigos `error` por status HTTP:

| Status | `error` |
| ------ | ------- |
| 400 | `bad_request` |
| 401 | `unauthorized` |
| 403 | `forbidden` · `insufficient_permissions` |
| 404 | `not_found` |
| 405 | `method_not_allowed` |
| 409 | `conflict` |
| 429 | `throttled` |
| 500 | `internal_error` |
| 503 | `service_unavailable` |

Errores específicos del middleware de autenticación:

| `error` | Status | Causa |
| ------- | ------ | ----- |
| `missing_token` | 401 | No hay cabecera `Authorization` |
| `invalid_token` | 401 | JWT inválido, expirado o respuesta inesperada del auth service |
| `unauthorized` | 403 | Auth service devolvió 403 |
| `user_not_found` | 404 | Auth service devolvió 404 |
| `service_unavailable` | 503 | Auth service no responde o devuelve 5xx |
| `missing_service_key` | 401 | `X-Service-Api-Key` presente pero vacío |
| `invalid_service_key` | 403 | `X-Service-Api-Key` no coincide |
| `missing_user_id` | 400 | Falta `X-User-Id` al usar service key |
| `invalid_user_id` | 400 | `X-User-Id` no es entero |
| `missing_user_email` | 400 | Falta `X-User-Email` al usar service key |

---

## Throttling

Configurado en `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` de `base.py`:

| Scope | Límite (producción) |
| ----- | ------------------- |
| `anon` | 60 req/minuto |
| `user` | 240 req/minuto |
| `internal` | 120 req/minuto (endpoint `/internal/events/`) |

En el settings de desarrollo estos límites están relajados a 600/1200 req/minuto para no interferir con pruebas.

Al superar el límite → **429** con `error: throttled` y cabecera `Retry-After`.
