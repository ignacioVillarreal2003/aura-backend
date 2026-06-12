# Autenticación

Todas las peticiones a rutas **no excluidas** pasan por el middleware de autenticación antes de llegar a los controladores. Las respuestas de error por autenticación siguen el mismo estilo que el proveedor FastAPI del proyecto (cuerpo JSON con `detail` y `error`).

## Usuario interactivo: Bearer JWT

1. El cliente envía **`Authorization: Bearer <token>`**.
2. El servicio valida el token con una petición **GET** a la URL configurada en **`AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`** (definida en la configuración del proveedor de autenticación, prefijo de entorno `AUTHENTICATION_PROVIDER_`).
3. Si la respuesta es correcta, el cuerpo JSON debe permitir construir el usuario autenticado (identificador, email, roles y permisos según lo que devuelva el servicio de auth).

Errores habituales (forma orientativa; ver mensajes reales en la respuesta):

- Token ausente o no Bearer → **401** con código tipo `missing_token`.
- Token inválido o expirado → **401** con código tipo `invalid_token`.
- Acceso denegado por el servicio de auth → **403** con código tipo `unauthorized`.
- Usuario no encontrado → **404** con código tipo `user_not_found`.
- Auth service no disponible o timeout → **503** con código tipo `service_unavailable`.

## Servicio a servicio

Si se envía la cabecera **`X-Service-Api-Key`**:

- La clave debe coincidir con **`SERVICE_API_KEY`** (configuración de la aplicación).
- Si la clave está presente pero vacía → **401** (`missing_service_key`).
- Si la clave no coincide → **403** (`invalid_service_key`).
- Deben enviarse también **`X-User-Id`** (entero) y **`X-User-Email`** (no vacío); si faltan o son inválidos → **400** con códigos `missing_user_id`, `invalid_user_id` o `missing_user_email`.
- Opcionales: **`X-User-Roles`** y **`X-User-Permissions`** como listas separadas por comas.

En este modo no hace falta Bearer; el usuario efectivo de la petición es el indicado por las cabeceras.

## Peticiones OPTIONS

Las peticiones **`OPTIONS`** no pasan por validación de token ni de cabeceras de servicio; se delegan al resto de la cadena (p. ej. CORS).

## Rutas sin autenticación (exclusiones)

Las siguientes rutas **no** exigen autenticación en el middleware (lista alineada con `_EXCLUDED_PATHS` en la configuración):

| Ruta |
|------|
| `/` |
| `/api/v1/health` |
| `/api/v1/ready` |
| `/api/docs` |
| `/api/redoc` |
| `/api/openapi.json` |
| `/metrics` |

Nota: la exclusión solo significa que **no** se exige Bearer ni cabeceras de servicio en esa ruta; `/api/v1/health` y `/api/v1/ready` quedan abiertas para las probes de liveness/readiness del orquestador.

## Errores de dominio y validación (después de autenticar)

Una vez autenticada la petición, los controladores pueden devolver errores con el manejador de excepciones de la aplicación (p. ej. validación **422** con `detail` en el cuerpo, o errores de negocio con códigos y mensajes propios). El detalle exacto figura en OpenAPI y en el código de `exception_handlers`.
