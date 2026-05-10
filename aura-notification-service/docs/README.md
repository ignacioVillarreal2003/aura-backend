# Aura Notification Service — Guía de la API

Documentación orientada a desarrolladores que integran frontends u otros microservicios con este servicio. La API base vive bajo **`/api/v1/`**. El contrato detallado (OpenAPI) está en tiempo de ejecución en **`/api/docs/`** (Swagger) y **`/api/redoc/`** (ReDoc).

---

## Tabla de contenidos

1. [Qué hace este servicio](#qué-hace-este-servicio)
2. [Arquitectura de alto nivel](#arquitectura-de-alto-nivel)
3. [Autenticación](#autenticación)
4. [Endpoints por público](#endpoints-por-público)
5. [Productores internos: emitir eventos](#productores-internos-emitir-eventos)
6. [Idempotencia y datos](#idempotencia-y-datos)
7. [Tiempo real in-app (SSE)](#tiempo-real-in-app-sse)
8. [Rendimiento y consumo de recursos](#rendimiento-y-consumo-de-recursos)
9. [Tipos de evento y email](#tipos-de-evento-y-email)
10. [Referencias rápidas en el repo](#referencias-rápidas-en-el-repo)

---

## Qué hace este servicio

Es el **centro de notificaciones** de Aura. Los demás microservicios **no** envían correos ni montan una bandeja propia sobre la base compartida: en su lugar envían **eventos semánticos** (por ejemplo `chat.member.invited`, `document.processing.done`). Este servicio:

1. Decide **canal(es)** (**in-app**, **email**) según el **registro de eventos** y las **preferencias** del usuario.
2. **Persiste** las notificaciones in-app en Postgres.
3. **Encola** emails en **Celery + RabbitMQ** (plantillas Django, SMTP con reintentos).
4. **Publica deltas** por usuario en **Redis pub/sub**, que el proceso HTTP convierte en **Server-Sent Events (SSE)** hacia el navegador.

Así separás “algo pasó en el dominio” (evento) de “cómo se muestra” (plantillas, enlaces, canales permitidos).

---

## Arquitectura de alto nivel

```
producer (chat / auth / docs)
        │  POST /api/v1/internal/events
        ▼
  aura-notification-service
        │ resuelve preferencias + plantillas
        ├──► Postgres (notification, dispatch, preferences)
        ├──► Redis pub/sub → GET /api/v1/notifications/stream/ → Frontend (SSE)
        └──► RabbitMQ → Celery worker → SMTP
```

---

## Autenticación

Hay tres formas típicas de llamar al servicio. La clase concreta de middleware está en `core/authentication/` y las rutas públicas/internal en `AUTHENTICATION_EXCLUDED_PATHS` dentro de `aura_notification_service/settings/base.py`.

### 1. Usuario final — `Authorization: Bearer <JWT>`

- El middleware valida el JWT contra el servicio de autenticación central (`AUTHENTICATION_SERVICE_URL`, habitualmente **`/auth/validate`**).
- Inbox, preferencias y SSE revisan **`AccessControl.require_permissions`** con **un único permiso por endpoint** (strings en el JWT, ver tabla más abajo; definiciones en `core/authorization/permissions.py`).

### 2. Otro microservicio “suplantando” al usuario — `X-Service-Api-Key`

- Convención alineada con el resto de Aura: **`X-Service-Api-Key`** igual a **`SERVICE_API_KEY`**, más cabeceras como **`X-User-Id`** (y relacionadas como email, roles y permisos cuando apliquen).
- Sirve cuando el gateway o servicio downstream **ya validó identidad** y reenvía la petición como si fuera el usuario, sin Bearer en el navegador.

Implementación de referencia: `core/authentication/authentication_provider.py`.

### 3. Servicio backend sin JWT en la petición — `X-Internal-Token`

Usado por **productores de eventos** y endpoints internos catalogados como “internal” en OpenAPI.

- Rutas bajo **`/api/v1/internal/*`** y **`/api/internal/*`** **no pasan** por la validación JWT del middleware (`AUTHENTICATION_EXCLUDED_PATHS`).
- La vista comprueba **`X-Internal-Token`** con **`NOTIFICATION_INTERNAL_API_TOKEN`** mediante comparación en tiempo constante (`hmac.compare_digest`) para evitar timing attacks (`apps/notification/api/views/internal_views.py`).

---

## Endpoints por público

Las URLs efectivas combinan el prefijo (`/api/v1/` + path en `apps/notification/api/urls.py`) más las rutas de documentación en `aura_notification_service/urls.py`.

### Usuario final (JWT o equivalente via service key)

| Método | Ruta | Permiso JWT (`permissions`) | Descripción breve |
| ------ | ---- | ----------------------------- | ----------------- |
| `GET` | `/api/v1/notifications/` | `NOTIFICATION_INBOX_LIST` | Bandeja paginada (`status`, `event_type`, `type`, `since`, `unread_only`, paginación) |
| `GET` | `/api/v1/notifications/unread-count/` | `NOTIFICATION_UNREAD_COUNT_GET` | `{ "count": <int> }` |
| `GET` | `/api/v1/notifications/{id}/` | `NOTIFICATION_DETAIL_GET` | Detalle |
| `PATCH` | `/api/v1/notifications/{id}/` | `NOTIFICATION_STATUS_PATCH` | Estado: `read` \| `unread` \| `archived` |
| `DELETE` | `/api/v1/notifications/{id}/` | `NOTIFICATION_SOFT_DELETE` | Borrado **soft** |
| `DELETE` | `/api/v1/notifications/{id}/hard/` | `NOTIFICATION_HARD_DELETE` | Borrado **hard** |
| `POST` | `/api/v1/notifications/mark-all-read/` | `NOTIFICATION_MARK_ALL_READ_POST` | Cuerpo opcional `{ "until_id": <int> }` |
| `GET` | `/api/v1/notifications/stream/` | `NOTIFICATION_STREAM_SUBSCRIBE` | **SSE** — deltas in-app en tiempo casi real |
| `GET` | `/api/v1/me/notification-preferences/` | `NOTIFICATION_PREFERENCES_GLOBAL_GET` | Preferencias globales (lectura) |
| `PUT` | `/api/v1/me/notification-preferences/` | `NOTIFICATION_PREFERENCES_GLOBAL_PUT` | Preferencias globales (mute, quiet hours, toggles globales) |
| `GET` | `/api/v1/me/notification-preferences/event-types/` | `NOTIFICATION_PREFERENCES_EVENT_TYPES_GET` | Matriz por tipo de evento + metadatos |
| `PUT` | `/api/v1/me/notification-preferences/event-types/{event_type}/` | `NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT` | Toggle por canal (`inapp_enabled`, `email_enabled`) |

El central auth debe emitir en el JWT la cadena exacta de cada permiso. Para usuarios estándar con inbox completa, conviene agruparlos desde el lado de autorización (roles que incluyen este conjunto) en lugar de listarlos cliente a cliente.

Serializers de ejemplo: `apps/notification/api/serializers/` (`notification.py`, `preferences.py`).

### Anónimo (sin token)

| Método | Ruta | Uso típico |
| ------ | ---- | ---------- |
| `GET` | `/api/v1/event-types/` | Catálogo de tipos soportados para armar pantallas de preferencias |
| `GET` | `/api/v1/health` | Salud del servicio y dependencias |
| `GET` | `/api/schema/` | Esquema OpenAPI |
| `GET` | `/api/docs/` / `/api/redoc/` | Exploradores de API |

### Internos (`X-Internal-Token`)

| Método | Ruta | Notas |
| ------ | ---- | ----- |
| `POST` | `/api/v1/internal/events/` | **Entrada recomendada** para productores |
| `POST` | `/api/v1/internal/notifications/admin-create/` | Payload legacy/admin → canal que termina como `admin.broadcast` |
| `POST` | `/api/internal/notification/admin-create/` | **Alias legacy** que sigue usando `aura-auth-service` |
| `POST` | `/api/internal/notifications/admin-create/` | Alias defensiva (algunos callers usaron plural) |

---

## Productores internos: emitir eventos

**`POST /api/v1/internal/events/`**

Cabeceras:

```http
Content-Type: application/json
X-Internal-Token: <NOTIFICATION_INTERNAL_API_TOKEN>
```

Campos más importantes del cuerpo (validados en `EventEmissionRequestSerializer`, `apps/notification/api/serializers/events.py`):

| Campo | Obligatorio | Notas |
| ----- | ----------- | ----- |
| `event_type` | Sí | Debe existir en el registro (`is_known_event`) |
| `recipient_ids` | Sí | Lista de enteros positivos (hasta **10 000** por request) |
| `actor_id` | No | Quién causó la acción |
| `actor_name` | No | Nombre visible |
| `context` | No | Dict libre para plantillas y texto enriquecido |
| `idempotency_key` | No | Clave estable para deduplicar (`event_key` en BD para filas activas) |
| `link_url` | No | Deep link opcional para la UI |
| `channels_override` | No | Lista `["inapp"]` / `["email"]` cuando quieras forzar canales |
| `target_scope` / `target_label` | No | Metadatos de agrupación/“target” en la UI |

**Respuesta típica** — `201 Created` con por receptor `outcomes` (estado por canal), más resumen: `created`, `suppressed`, `skipped`, `pending_email`.

**Ejemplo mínimo** (ajustá host y token):

```http
POST /api/v1/internal/events/ HTTP/1.1
Host: aura-notification-service:8000
Content-Type: application/json
X-Internal-Token: dev-notification-internal-token

{
  "event_type": "chat.member.invited",
  "recipient_ids": [12, 13],
  "actor_id": 7,
  "actor_name": "usuario.ejemplo",
  "context": {
    "chat_id": 42,
    "chat_name": "Proyecto X",
    "recipient_email": "alguien@ejemplo.com"
  },
  "idempotency_key": "chat-42-invite-12-2026-05-09",
  "link_url": "https://app.ejemplo.com/chats/42"
}
```

Si ya enviás **`recipient_email`** dentro de **`context`** cuando el canal email está activo, el worker puede ahorrar un round-trip al auth para obtener el correo (ver también la tabla de variables en el `README.md` raíz).

---

## Idempotencia y datos

- **`idempotency_key`** alimenta el **`event_key`** en base de datos junto al **`receiver_id`**, evitando duplicados sobre filas activas (índice único parcial documentado en el `README.md` del proyecto).
- El DDL operativo está en **`sql/schema.sql`**; los modelos Django usan **`managed = False`** y no son la fuente de verdad migratoria.
- Mantenimiento: comando `purge_notifications` para borrado físico de soft-deletes antiguos (ver `README.md`).

---

## Tiempo real in-app (SSE)

Las notificaciones **in-app** se listan como cualquier recurso REST, pero los **push** hacia la UI cliente van por **`GET /api/v1/notifications/stream/`** con Bearer JWT del **mismo usuario** destinatario (`receiver`).

### Cómo funciona por dentro

1. Cuando cambia una notificación relevante para un usuario, el dispatcher usa **`RealtimeService`** (`apps/notification/services/realtime_service.py`) que publica en Redis **`publish_user_event(user_id, { "event", "data" })`**.
2. **`NotificationStreamView`** (`apps/notification/api/views/stream_view.py`) está suscrito al canal Redis de ese **`user_id`** y **traduce cada mensaje JSON a un frame SSE**:
   - Líneas `event: <nombre>`
   - Líneas `data: <JSON por línea si el payload es multilínea>`
3. Mantenimiento de conexión: comentarios **`: keepalive`** de forma periódica (**`NOTIFICATION_SSE_HEARTBEAT_SECONDS`**, típicamente ~15 s).

### Tipos SSE que verás habitualmente

| Evento SSE | Significado práctico |
| ---------- | --------------------- |
| `stream.opened` | Conexión establecida; incluye datos como `user_id` |
| `notification.created` | Nueva fila in-app |
| `notification.updated` | Cambio en una notificación ya existente |
| `notification.deleted` | Se eliminó (típicamente `{ "id": ... }`) |
| `stream.closed` | El servidor cerró el stream tras **`NOTIFICATION_SSE_MAX_DURATION_SECONDS`** (reconectar) |
| `stream.error` | Error interno recuperable antes de cerrar |

Si el campo interno viene sin `event`, el stream usa **`notification.update`** como nombre por defecto.

### Contrato cliente (frontend)

1. **`EventSource`** o `fetch` + lectura incremental con **`Accept: text/event-stream`** (`curl -N` sirve para pruebas locales).
2. Al abrir **`stream.closed`**, abrir una **nueva** conexión (el ciclo típico con timeout de ~30 min configurables).
3. **Sin SSE abierta** la notificación **sigue persistida**: al volver a la app cargá **`GET /api/v1/notifications/`**; el stream solo evita refrescos constantes mientras hay sesión.

### Email vs SSE

**El correo no pasa por el stream SSE.** El email se encola y sale por worker (**RabbitMQ → Celery → SMTP**). El SSE es solo para deltas de la bandeja in-app en el navegador.

---

## Rendimiento y consumo de recursos

- Por cada usuario/pestaña con stream abierta hay **una conexión HTTP larga**, **una suscripción Redis** práctica sobre el usuario, y ocupación proporcional del worker/app server.
- El tráfico es **liviano**: heartbeats cortos más **JSON solo cuando algo cambió** — muchas veces mejor que hacer **polling REST** cada pocos segundos.
- Múltiples pestañas = **varias conexiones** del mismo usuario.
- A muy alta concurrente sólo SSE, tocá tamaño del pool Gunicorn/uvicorn, timeouts del balanceador (**`X-Accel-Buffering: no`** ya viene en la respuesta SSE para proxies tipo nginx).

---

## Tipos de evento y email

Los tipos válidos (`event_type`), canales por defecto, si el usuario puede silenciarlos y el **template id** viven en **`apps/notification/events/registry.py`**. Una tabla orientativa aparece también en **`README.md`** en la raíz del servicio (`chat.*`, `auth.*`, `document.*`, `admin.broadcast`, `system.announcement`, etc.). Las plantillas HTML/texto van bajo **`apps/notification/templates/notifications/<template_id>/`**.

Para añadir un evento nuevo: constante **`EventType`**, entrada **`_EVENTS`** en registry, y plantillas asociadas.

---

## Referencias rápidas en el repo

| Qué necesitás | Dónde mirar |
| ------------- | ----------- |
| Mapa HTTP v1 | `apps/notification/api/urls.py` |
| Middleware JWT / exclusiones | `core/authentication/authentication_middleware.py`, settings `AUTHENTICATION_EXCLUDED_PATHS` |
| Internal token & productores | `apps/notification/api/views/internal_views.py` |
| SSE y formato | `apps/notification/api/views/stream_view.py` |
| Publicación tiempo real Redis | `core/pubsub/redis_pubsub.py`, `RealtimeService` |
| Variables de entorno | `.env`, `.env.docker`, `README.md` |
| DDL | `sql/schema.sql` |

---

*Última revisión orientada al código vigente del servicio (`aura-notification-service`). Para payloads exactos y códigos de error, usar siempre **`/api/docs/`**.*
