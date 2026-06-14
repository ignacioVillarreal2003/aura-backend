# API interna para productores — `POST /api/v1/internal/events/`

Vista: `apps/notification/api/views/internal_views.py`  
Serializer: `apps/notification/api/serializers/events.py`  
Servicio: `apps/notification/services/dispatch_service.py`

Endpoint para que otros microservicios de la plataforma emitan notificaciones para uno o varios usuarios. La ruta está excluida del JWT (`AUTHENTICATION_EXCLUDED_PATHS`); la seguridad es el token interno.

---

## Autenticación

```http
POST /api/v1/internal/events/ HTTP/1.1
Host: aura-notification-service:8000
Content-Type: application/json
X-Internal-Token: <NOTIFICATION_INTERNAL_API_TOKEN>
```

El token se compara con `hmac.compare_digest` para evitar timing attacks. Si no coincide → **401**.

Throttle: **120 req/minuto** por IP (`scope = "internal"`).

---

## Request body

```json
{
  "event_type": "chat.member.invited",
  "recipient_ids": [12, 13, 14],
  "actor_id": 7,
  "actor_name": "usuario.ejemplo",
  "context": {
    "chat_id": 42,
    "chat_name": "Proyecto X",
    "recipient_email": "destinatario@ejemplo.com"
  },
  "link_url": "https://app.ejemplo.com/chats/42"
}
```

### Campos

| Campo | Requerido | Tipo | Validación |
| ----- | --------- | ---- | ---------- |
| `event_type` | Sí | string | ≤ 128 chars · debe existir en el registro de eventos |
| `recipient_ids` | Sí | lista de enteros | Cada ID ≥ 1 · entre 1 y **10 000** destinatarios por request |
| `actor_id` | No | entero \| null | ≥ 1 si se envía |
| `actor_name` | No | string | ≤ 255 chars · puede ser vacío |
| `context` | No | objeto | JSON libre para plantillas, links y texto |
| `link_url` | No | URL | URL válida o vacío |

### Sobre `context`

El diccionario `context` se usa para:
- Renderizar las plantillas de texto e email (Django templates bajo `templates/notifications/<template_id>/`).
- Construir el `link_url` automáticamente si el evento tiene un `link_builder` (p. ej. `chat_id` para eventos de chat, `document_id` para eventos de documentos).
- Guardarse como campo `data` en la notificación (visible en la bandeja del usuario).

**Optimización para email:** si `context` incluye `recipient_email`, el worker de email usa ese valor directamente sin necesitar un round-trip al servicio de autenticación para obtener el correo del destinatario.

---

## Respuesta `201 Created`

```json
{
  "event_type": "chat.member.invited",
  "created": 2,
  "skipped": 1,
  "pending_email": 0,
  "outcomes": [
    {
      "receiver_id": 12,
      "notification_id": 501,
      "channels": {
        "inapp": "sent"
      }
    },
    {
      "receiver_id": 13,
      "notification_id": 502,
      "channels": {
        "inapp": "sent"
      }
    },
    {
      "receiver_id": 14,
      "notification_id": null,
      "channels": {
        "inapp": "skipped"
      }
    }
  ]
}
```

### Resumen numérico

| Campo | Descripción |
| ----- | ----------- |
| `created` | Notificaciones in-app nuevas creadas |
| `skipped` | Canales omitidos por preferencias del usuario (mute, canal deshabilitado, evento no configurado para ese canal) |
| `pending_email` | Emails encolados en Celery (estado `pending`) |

### Por receptor (`outcomes`)

| Campo | Descripción |
| ----- | ----------- |
| `receiver_id` | ID del destinatario |
| `notification_id` | ID de la fila en Postgres, o `null` si no se creó in-app |
| `channels` | Mapa de canal → estado de despacho |

### Estados de despacho por canal (`channels`)

| Estado | Descripción |
| ------ | ----------- |
| `sent` | In-app creada y publicada en tiempo real |
| `pending` | Email encolado en Celery, aún no enviado |
| `skipped` | Canal omitido por preferencias del usuario |
| `failed` | Falló el encolado del email (registrado en `email_dispatch`) |

---

## Errores

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 401 | `unauthorized` | `X-Internal-Token` ausente o incorrecto |
| 400 | `bad_request` | Campos faltantes, `event_type` desconocido, `recipient_ids` vacío o inválido |
| 429 | `throttled` | Límite de 120 req/minuto superado |

---

## Ejemplos por caso de uso

### Notificación de chat a múltiples usuarios

```json
{
  "event_type": "chat.member.invited",
  "recipient_ids": [10, 20, 30],
  "actor_id": 5,
  "actor_name": "admin.user",
  "context": { "chat_id": 99, "chat_name": "Equipo de diseño" }
}
```

### Email de seguridad (no silenciable, siempre se entrega)

```json
{
  "event_type": "auth.password.changed",
  "recipient_ids": [42],
  "context": {
    "recipient_email": "usuario@ejemplo.com",
    "recipient_name": "Usuario Ejemplo"
  }
}
```

### Anuncio administrativo

```json
{
  "event_type": "admin.broadcast",
  "recipient_ids": [1, 2, 3, 4, 5],
  "actor_name": "Equipo Aura",
  "context": { "message": "Mantenimiento programado el viernes a las 22:00 hs." }
}
```

---

## Broadcast administrativo

Para enviar un anuncio masivo usar `event_type: "admin.broadcast"` con todos los `recipient_ids` requeridos. No existe un endpoint separado para broadcasts; el mismo endpoint soporta hasta **10 000 destinatarios por request**.
