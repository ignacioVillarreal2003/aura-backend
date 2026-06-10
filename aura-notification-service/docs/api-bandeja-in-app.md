# API de bandeja in-app — `/api/v1/notifications/`

Vistas: `apps/notification/api/views/notification_views.py`  
Serializers: `apps/notification/api/serializers/notification.py`  
Servicio: `apps/notification/services/notification_service.py`

Todas las operaciones actúan sobre las notificaciones del **usuario autenticado**. Las filas con soft-delete (`deleted_at IS NOT NULL`) no aparecen en ningún endpoint de usuario.

---

## Modelo de una notificación

Todos los endpoints de lectura devuelven objetos con los siguientes campos:

| Campo | Tipo | Descripción |
| ----- | ---- | ----------- |
| `id` | entero | ID de la notificación |
| `receiver_id` | entero | ID del usuario destinatario |
| `event_type` | string | Identificador del evento (p. ej. `chat.member.invited`) |
| `message` | string (≤ 500) | Texto renderizado de la notificación |
| `data` | objeto | Contexto original del evento (para uso del frontend) |
| `severity` | string | `info` · `success` · `warning` · `critical` |
| `link_url` | string \| null | Deep link opcional para la UI |
| `actor_name` | string \| null | Nombre del actor que generó la notificación |
| `status` | string | `unread` · `read` |
| `read_at` | datetime \| null | Momento en que se marcó como leída |
| `created_by` | entero \| null | ID del actor que disparó la notificación |
| `created_at` | datetime | Fecha de creación |

---

## `GET /api/v1/notifications/` — listado paginado

**Permiso:** `NOTIFICATION_INBOX_LIST`

### Query params

| Parámetro | Tipo | Descripción |
| --------- | ---- | ----------- |
| `status` | string, repetible | Filtra por estado. Se puede repetir: `?status=unread&status=read` |
| `event_type` | string | Filtra por tipo de evento exacto |
| `since` | datetime ISO 8601 | Solo notificaciones con `created_at >= valor` (p. ej. `2024-01-15T10:30:00Z`) |
| `page` | entero | Número de página (base 1) |
| `page_size` | entero | Resultados por página. Por defecto **20**, máximo **100** |

### Respuesta `200`

```json
{
  "count": 47,
  "next": "/api/v1/notifications/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "receiver_id": 42,
      "event_type": "chat.member.invited",
      "message": "Te invitaron al chat Proyecto X",
      "data": { "chat_id": 15, "chat_name": "Proyecto X" },
      "severity": "info",
      "link_url": "https://app.ejemplo.com/chats/15",
      "actor_name": "otro.usuario",
      "status": "unread",
      "read_at": null,
      "created_by": 7,
      "created_at": "2024-05-10T14:23:00Z"
    }
  ]
}
```

---

## `GET /api/v1/notifications/unread-count/`

**Permiso:** `NOTIFICATION_UNREAD_COUNT_GET`

Cuenta notificaciones con `status = unread` del usuario, excluyendo soft-deletes.

### Respuesta `200`

```json
{ "count": 5 }
```

---

## `GET /api/v1/notifications/{id}/`

**Permiso:** `NOTIFICATION_DETAIL_GET`

Devuelve una notificación perteneciente al usuario autenticado.

**Errores:**

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 404 | `notification_not_found` | No existe o pertenece a otro usuario |

---

## `PATCH /api/v1/notifications/{id}/`

**Permiso:** `NOTIFICATION_STATUS_PATCH`

Cambia el estado de una notificación del usuario autenticado.

### Request body

```json
{ "status": "read" }
```

Valores válidos para `status`: `unread` · `read`

Tras el cambio el servicio publica un evento en tiempo real (SSE `notification.updated`) con `{ "id": <id>, "status": <nuevo_status> }`.

### Respuesta `200`

El objeto completo de la notificación con el estado actualizado.

**Errores:**

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 400 | `bad_request` | `status` inválido |
| 404 | `notification_not_found` | No existe o pertenece a otro usuario |

---

## `DELETE /api/v1/notifications/{id}/`

**Permiso:** `NOTIFICATION_SOFT_DELETE`

Marca la notificación como eliminada (`deleted_at = now()`). La fila sigue en la base de datos pero deja de aparecer en todos los endpoints de usuario. El servicio publica un evento SSE `notification.deleted`.

### Respuesta `204` — sin cuerpo

**Errores:**

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 404 | `notification_not_found` | No existe o pertenece a otro usuario |

---

## `POST /api/v1/notifications/mark-all-read/`

**Permiso:** `NOTIFICATION_MARK_ALL_READ_POST`

Marca como leídas todas las notificaciones `unread` del usuario. Acepta un cuerpo vacío `{}` o con `until_id`.

### Request body (opcional)

```json
{ "until_id": 200 }
```

Si `until_id` está presente, solo se marcan las notificaciones con `id <= until_id`. `until_id` debe ser un entero ≥ 1.

### Respuesta `200`

```json
{ "updated": 12 }
```

Si hubo filas actualizadas, el servicio publica un evento SSE `notification.updated` con `{ "all_marked_read": true, "until_id": 200, "count": 12 }`.

---

## Cambios en tiempo real

Los endpoints `PATCH`, `DELETE` y `mark-all-read` publican eventos en Redis que el stream SSE convierte en frames para el frontend. Ver [api-tiempo-real-sse.md](./api-tiempo-real-sse.md) para el formato completo.
