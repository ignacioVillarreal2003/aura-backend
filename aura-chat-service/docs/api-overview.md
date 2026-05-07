# Características generales de la API

## Base URL y versionado

- Los recursos REST del producto están bajo el prefijo **`/api/v1/`**.
- La versión del documento OpenAPI (`version` en el schema) viene de **`APP_VERSION`** en `aura_chat_service/settings/base.py`; la versión **de la ruta** (`v1`) es la que fija compatibilidad para clientes.

## Autenticación y permisos

- **Por defecto** las vistas usan `IsAuthenticated` (Django REST framework): se espera un usuario autenticado en la petición.
- El middleware de autenticación resuelve el usuario (p. ej. vía JWT) y adjunta permisos de aplicación al objeto de usuario.
- Casi cada operación llama internamente a `AccessControl.require_permissions` con **strings de permiso** (p. ej. `LIST_CHATS`, `SEND_MESSAGE`). El token o la identidad que entrega el auth-service debe incluir el conjunto adecuado; si falta alguno, la API responde **403** con cuerpo de error estándar (`insufficient_permissions`).
- Detalle por constante: [permissions.md](permissions.md).

Header típico:

```http
Authorization: Bearer <JWT>
```

Los detalles del emisor de tokens y el modelo de usuarios no son responsabilidad de este servicio; aquí solo se documenta **qué permiso lógico** exige cada ruta.

## Rutas sin autenticación de aplicación

Configuración referencial (`AUTHENTICATION_EXCLUDED_PATHS` en settings); incluye entre otras:

| Ruta (patrón) | Uso |
|----------------|-----|
| `/api/v1/health` | Health check (DB + Redis). |
| `/api/schema*`, `/api/docs*`, `/api/redoc*` | Documentación OpenAPI y UIs. |
| `/api/v1/share*` | Lectura pública de mensajes vía **token** en la URL (sin Bearer de usuario). |
| `/metrics` | Métricas Prometheus (operación). |
| `/admin/*` | Django admin. |

El **WebSocket** del chat usa otro mecanismo (middleware de Channels + scope); ver [websockets.md](websockets.md).

## Formato de datos

- **Entrada y salida:** JSON (`Content-Type: application/json`), salvo exportaciones que devuelven PDF, Markdown, JSON archivo, etc., con los `Content-Type` adecuados.
- **Errores:** cuerpo JSON coherente descrito en [errors-and-status-codes.md](errors-and-status-codes.md): campos `error`, `detail`, `status_code`; en validación 400 pueden aparecer `fields`.

## Paginación

- **Paginación por página** (`StandardPagination`): parámetros `page` y opcionalmente `page_size` (máximo **100** por defecto), tamaño de página por defecto **20**. Se usa en listados de chats, miembros, webhooks, share links, mensajes fijados, etc., según la vista.
- **Paginación por cursor** (`MessageCursorPagination`): usada en algunos listados de mensajes (historial con orden temporal); parámetros al estilo DRF `cursor` / `page_size` (máx. **100**), orden por defecto `-created_at`.

Los detalles de cada lista están en el esquema OpenAPI y en [endpoints.md](endpoints.md).

## OpenAPI (drf-spectacular)

- El contrato oficial (schemas, enums, parámetros de query como `search`, `ordering`, `tags`) se genera con **drf-spectacular**.
- Para integraciones automáticas (clientes generados, pruebas de contrato), priorizar **`GET /api/schema/`**; la documentación en Markdown en esta carpeta prioriza **legibilidad** y **permisos**.

## CORS y límites de petición

- **CORS:** orígenes permitidos configurables (p. ej. `CORS_ALLOWED_ORIGINS`); credenciales pueden estar habilitadas según settings.
- **Throttling:** valores por defecto del proyecto (p. ej. anon/usuario por minuto) en `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`; respuesta **429** si se excede.

## Observabilidad

- **Correlation ID:** middleware de correlación en peticiones HTTP (útil para trazar logs con el gateway o el cliente).
- **Métricas:** endpoint de Prometheus en `/metrics` (no forma parte de la API JSON de negocio).

## Membresía y recursos

Muchas operaciones sobre un `chat_id` exigen, además del permiso lógico, ser **miembro activo** del chat (o que el recurso exista). En esos casos la API puede responder **404** (no encontrado / sin acceso) según la lógica de cada servicio. Eso no sustituye al permiso: primero identidad y permisos, luego reglas de dominio.
