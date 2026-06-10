# Aura Notification Service — Guía de la API

Documentación para desarrolladores que integran frontends u otros microservicios. Prefijo base: **`/api/v1/`**. Documentación modular por tema en [`docs/INDEX.md`](./INDEX.md).

---

## Qué hace este servicio

Es el **centro de notificaciones** de la plataforma Aura. Los demás microservicios no gestionan correos ni bandeja propia: envían **eventos semánticos** a este servicio, que decide canales, persiste, envía emails y empuja deltas en tiempo real.

Flujo completo de una notificación:

1. Un microservicio productor llama a `POST /api/v1/internal/events/` con el tipo de evento y los destinatarios.
2. El servicio consulta las **preferencias globales** de cada usuario (canal habilitado, mute) y decide si entrega por **in-app**, **email** o ambos.
3. Si corresponde in-app: crea una fila en Postgres y publica en **Redis pub/sub** → el frontend la recibe por **SSE** sin polling.
4. Si corresponde email: crea una fila de despacho `PENDING` y encola una tarea en **RabbitMQ** → el worker Celery renderiza la plantilla y envía por SMTP con reintentos automáticos.

---

## Arquitectura

```
microservicio productor
        │  POST /api/v1/internal/events/
        │  X-Internal-Token: <token>
        ▼
aura-notification-service (Django/Gunicorn)
        │
        ├── PreferenceService  →  ¿entrego? ¿por qué canal?
        ├── TemplateService    →  renderiza mensaje e email
        │
        ├── Postgres           ←  notification + email_dispatch + notification_preference
        │
        ├── Redis pub/sub      →  NotificationStreamView (SSE)  →  navegador
        │
        └── RabbitMQ           →  Celery worker  →  SMTP
```

---

## Mapa de endpoints

### Usuario final (JWT o service key con usuario)

| Método | Ruta | Permiso requerido |
| ------ | ---- | ----------------- |
| `GET` | `/api/v1/notifications/` | `NOTIFICATION_INBOX_LIST` |
| `GET` | `/api/v1/notifications/unread-count/` | `NOTIFICATION_UNREAD_COUNT_GET` |
| `GET` | `/api/v1/notifications/{id}/` | `NOTIFICATION_DETAIL_GET` |
| `PATCH` | `/api/v1/notifications/{id}/` | `NOTIFICATION_STATUS_PATCH` |
| `DELETE` | `/api/v1/notifications/{id}/` | `NOTIFICATION_SOFT_DELETE` |
| `POST` | `/api/v1/notifications/mark-all-read/` | `NOTIFICATION_MARK_ALL_READ_POST` |
| `GET` | `/api/v1/notifications/stream/` | `NOTIFICATION_STREAM_SUBSCRIBE` |
| `GET` | `/api/v1/me/notification-preferences/` | `NOTIFICATION_PREFERENCES_GLOBAL_GET` |
| `PUT` | `/api/v1/me/notification-preferences/` | `NOTIFICATION_PREFERENCES_GLOBAL_PUT` |

### Sin autenticación

| Método | Ruta | Descripción |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/event-types/` | Catálogo público de tipos de evento |
| `GET` | `/api/v1/health` | Estado del servicio y dependencias |
| `GET` | `/api/schema/` | Esquema OpenAPI |
| `GET` | `/api/docs/` | Swagger UI |
| `GET` | `/api/redoc/` | ReDoc |

### Interna (`X-Internal-Token`)

| Método | Ruta | Descripción |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/internal/events/` | Emitir evento de notificación para uno o varios usuarios |

---

## Tipos de evento registrados

Definidos en `apps/notification/events/registry.py`.

| `event_type` | Severidad | Canales por defecto | Silenciable |
| ------------ | --------- | ------------------- | ----------- |
| `chat.member.invited` | `info` | `inapp` | Sí |
| `chat.member.removed` | `warning` | `inapp` | Sí |
| `chat.locked` | `warning` | `inapp` | Sí |
| `auth.password.changed` | `critical` | `inapp`, `email` | **No** |
| `auth.new_login` | `warning` | `inapp`, `email` | Sí |
| `document.processing.done` | `success` | `inapp` | Sí |
| `document.processing.failed` | `critical` | `inapp`, `email` | Sí |
| `admin.broadcast` | `info` | `inapp` | Sí |
| `system.announcement` | `info` | `inapp` | **No** |

Para agregar un evento nuevo: constante en `EventType`, entrada en `_EVENTS`, y plantillas bajo `templates/notifications/<template_id>/`.

---

## Referencias en el código

| Qué | Dónde |
| --- | ----- |
| Mapa de URLs | `apps/notification/api/urls.py` |
| Vistas de bandeja | `apps/notification/api/views/notification_views.py` |
| Vistas de preferencias | `apps/notification/api/views/preference_views.py` |
| Vista SSE | `apps/notification/api/views/stream_view.py` |
| Vista interna | `apps/notification/api/views/internal_views.py` |
| Dispatch completo | `apps/notification/services/dispatch_service.py` |
| Servicio de preferencias | `apps/notification/services/preference_service.py` |
| Redis pub/sub | `core/pubsub/redis_pubsub.py` |
| Auth middleware | `core/authentication/authentication_middleware.py` |
| Permisos | `core/authorization/permissions.py` |
| Variables de entorno | `.env` (local) · `.env.docker` (docker/producción) |
