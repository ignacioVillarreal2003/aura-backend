# Autenticación y permisos — Aura Document Collection Service

Dos capas encadenadas:

1. **Middleware de autenticación** (`AuthenticationMiddleware`): resuelve **quién** es el llamador y rellena `request.authenticated_user`, o bien responde con error HTTP antes de ejecutar la vista.
2. **Permisos DRF**: `DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated` — cualquier vista protegida exige usuario autenticado salvo marcado explícito (`AllowAny` solo en health en `urls.py`).
3. **Permisos de aplicación** (AUTORIZACIÓN MAC / negocio): cada servicio llama a `AccessControl.require_permissions` con constantes definidas en `core/authorization/permissions.py`.

---

## Mecanismo 1: Bearer JWT

- Cabecera: **`Authorization: Bearer <token>`**
- El servicio llama al **proveedor configurado** (`AUTHENTICATION_SERVICE_URL`) para validar el token y obtener el usuario.
- El JSON esperado incluye al menos **`id`** (usuario); opcionalmente `email`, `roles`, `permissions` (según respuesta real del proveedor; el código usa listas/tuple para roles y permissions).

Las **permissions** efectivas contra el modelo `AuthenticatedUser.has_all_permissions` son los **strings** que exponga el proveedor (o los enviados en headers S2S, ver abajo).

---

## Mecanismo 2: Service-to-service (API key + usuario actuante)

Cabeceras **obligatorias** cuando se usa esta vía:

| Cabecera | Descripción |
|----------|-------------|
| **`X-Service-Api-Key`** | Debe coincidir con `SERVICE_API_KEY` del despliegue. |
| **`X-User-Id`** | Entero: usuario en cuyo nombre actúa el servicio. |
| **`X-User-Email`** | Email del usuario actuante (texto no vacío tras trim). |

Cabeceras **opcionales**:

| Cabecera | Formato |
|----------|---------|
| **`X-User-Roles`** | Lista separada por comas. |
| **`X-User-Permissions`** | Lista separada por comas de códigos de permiso (los mismos que en la tabla inferior). |

**Orden de evaluación**: si está presente `X-Service-Api-Key` (no vacío), el middleware intenta autenticación S2S **antes** del Bearer. Si la clave no viene, se sigue con Bearer.

---

## Matriz permiso → endpoint

Los valores son los **strings exactos** que deben aparecer en `AuthenticatedUser.permissions` (Bearer desde auth service o `X-User-Permissions` en S2S).

### Document collections

| Permiso constante | String |
|-------------------|--------|
| Listar colecciones | `LIST_DOCUMENT_COLLECTIONS` |
| Crear colección | `CREATE_DOCUMENT_COLLECTION` |
| Obtener colección | `GET_DOCUMENT_COLLECTION` |
| Actualizar colección | `UPDATE_DOCUMENT_COLLECTION` |
| Eliminar colección | `DELETE_DOCUMENT_COLLECTION` |

### Documentos en colección (anidadas)

| Permiso constante | String |
|-------------------|--------|
| Listar enlaces | `LIST_DOCUMENT_COLLECTION_DOCUMENTS` |
| Añadir documento | `ADD_DOCUMENT_COLLECTION_DOCUMENT` |
| Quitar documento | `REMOVE_DOCUMENT_COLLECTION_DOCUMENT` |

### Classification levels

| Permiso constante | String |
|-------------------|--------|
| Listar | `LIST_CLASSIFICATION_LEVELS` |
| Crear | `CREATE_CLASSIFICATION_LEVEL` |
| Obtener | `GET_CLASSIFICATION_LEVEL` |
| Actualizar | `UPDATE_CLASSIFICATION_LEVEL` |
| Eliminar | `DELETE_CLASSIFICATION_LEVEL` |

### Compartments

| Permiso constante | String |
|-------------------|--------|
| Listar | `LIST_COMPARTMENTS` |
| Crear | `CREATE_COMPARTMENT` |
| Obtener | `GET_COMPARTMENT` |
| Actualizar | `UPDATE_COMPARTMENT` |
| Eliminar | `DELETE_COMPARTMENT` |

### User authorizations

| Permiso constante | String |
|-------------------|--------|
| Resumen de autorización | `GET_USER_AUTHORIZATION` |
| Asignar / actualizar clearance | `SET_USER_CLEARANCE` |
| Eliminar clearance | `DELETE_USER_CLEARANCE` |
| Listar compartimentos del usuario | `LIST_USER_COMPARTMENTS` |
| Añadir compartimento | `ADD_USER_COMPARTMENT` |
| Quitar compartimento | `REMOVE_USER_COMPARTMENT` |
| Colecciones accesibles (MAC) | `GET_USER_ACCESSIBLE_COLLECTIONS` |

---

## Comportamiento ante fallo de autorización de aplicación

Si el usuario está autenticado pero **no** tiene el permiso requerido, el servicio lanza **`InsufficientPermissionsException`**:

- HTTP **403**
- `error`: **`insufficient_permissions`**
- `detail`: mensaje estándar de falta de permiso

La comprobación es conjunto **exacto**: deben estar **todos** los permisos del `frozenset` requerido (cada endpoint pide uno).

---

## Rutas sin autenticación de middleware

Configuradas en `AUTHENTICATION_EXCLUDED_PATHS` (ejemplos):

- `/api/v1/health`
- `/metrics`
- `/admin/*` (patrón prefijo)
- `/api/schema*`, `/api/docs*`, `/api/redoc*`

En esas rutas **no** se fuerza Bearer/S2S a nivel de middleware; las vistas de negocio bajo `/api/v1/` **sí** están protegidas excepto `health`.

---

## OpenAPI / Swagger

Los esquemas de seguridad documentados coinciden con:

- **bearerAuth** (JWT)
- **serviceApiKey** + **serviceUserId** + **serviceUserEmail** (y roles/permissions opcionales en cabeceras adicionales descritas en `SPECTACULAR_SETTINGS`).

---

## Notas para integradores

- Un **gateway** o el **servicio de identidad** debe asegurar que los JWT incluyan el conjunto de `permissions` coherente con las operaciones que el cliente llamará.
- En **llamadas entre microservicios**, es habitual usar la API key compartida y reenviar **`X-User-Id`** / **`X-User-Email`** y la lista **`X-User-Permissions`** del contexto del usuario final.
