# Autenticación

Todas las peticiones a rutas **no excluidas** pasan por el middleware de autenticación antes de llegar a los controladores. Las respuestas de error por autenticación siguen el mismo estilo que el proveedor FastAPI del proyecto (cuerpo JSON con `detail` y `error`).

## Bearer JWT

1. El cliente envía **`Authorization: Bearer <token>`**.
2. El servicio busca el token en la caché de Redis; si está, usa los datos de usuario cacheados.
3. Si no está en caché, valida el token con una petición **GET** a la URL configurada en **`AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`** (definida en la configuración del proveedor de autenticación, prefijo de entorno `AUTHENTICATION_PROVIDER_`) y guarda el resultado en la caché.
4. Si la respuesta es correcta, el cuerpo JSON debe permitir construir el usuario autenticado (identificador, email, roles y permisos según lo que devuelva el servicio de auth).

Errores habituales (forma orientativa; ver mensajes reales en la respuesta):

- Token ausente o no Bearer → **401** con código tipo `missing_token`.
- Token inválido o expirado → **401** con código tipo `invalid_token`.
- Acceso denegado por el servicio de auth → **403** con código tipo `unauthorized`.
- Usuario no encontrado → **404** con código tipo `user_not_found`.
- Auth service no disponible o timeout → **503** con código tipo `service_unavailable`.

## Peticiones OPTIONS

Las peticiones **`OPTIONS`** no pasan por validación de token; se delegan al resto de la cadena (p. ej. CORS).

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

Nota: la exclusión solo significa que **no** se exige Bearer en esa ruta; `/api/v1/health` y `/api/v1/ready` quedan abiertas para las probes de liveness/readiness del orquestador.

## Errores de dominio y validación (después de autenticar)

Una vez autenticada la petición, los controladores pueden devolver errores con el manejador de excepciones de la aplicación (p. ej. validación **422** con `detail` en el cuerpo, o errores de negocio con códigos y mensajes propios). El detalle exacto figura en OpenAPI y en el código de `exception_handlers`.
