# API de preferencias de notificación

Vistas: `apps/notification/api/views/preference_views.py`  
Serializers: `apps/notification/api/serializers/preferences.py`  
Servicio: `apps/notification/services/preference_service.py`

Las preferencias controlan si un usuario recibe notificaciones y por qué canal. Si un usuario nunca configuró preferencias, el servicio opera con los valores por defecto del modelo (in-app habilitado, email habilitado, sin mute, sin quiet hours).

---

## `GET /api/v1/me/notification-preferences/`

**Permiso:** `NOTIFICATION_PREFERENCES_GLOBAL_GET`

Devuelve las preferencias globales del usuario autenticado.

### Respuesta `200`

```json
{
  "user_id": 42,
  "inapp_enabled": true,
  "email_enabled": true,
  "mute_until": null,
  "updated_at": "2024-05-10T20:00:00Z"
}
```

| Campo | Descripción |
| ----- | ----------- |
| `user_id` | Solo lectura |
| `inapp_enabled` | Si las notificaciones in-app están habilitadas globalmente |
| `email_enabled` | Si los emails están habilitados globalmente |
| `mute_until` | Datetime hasta el que todo está silenciado, o `null` |
| `updated_at` | Solo lectura |

---

## `PUT /api/v1/me/notification-preferences/`

**Permiso:** `NOTIFICATION_PREFERENCES_GLOBAL_PUT`

Actualiza preferencias globales. Todos los campos son opcionales: solo se actualizan los que se envíen.

### Request body

```json
{
  "inapp_enabled": true,
  "email_enabled": false,
  "mute_until": "2024-05-15T08:00:00Z"
}
```

### Reglas de validación

| Campo | Regla |
| ----- | ----- |
| `mute_until` | Debe ser un datetime **futuro**. Enviar `null` para eliminar el mute activo |

### Respuesta `200`

Mismo shape que el GET con los valores actualizados.

**Errores:**

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 400 | `bad_request` | `mute_until` en el pasado, timezone inválida, o enviar solo uno de start/end |

---

## `GET /api/v1/me/notification-preferences/event-types/`

**Permiso:** `NOTIFICATION_PREFERENCES_EVENT_TYPES_GET`

Devuelve el catálogo completo de tipos de evento con el estado efectivo por canal para el usuario autenticado. Combina los defaults del registro de eventos con los overrides guardados por el usuario.

### Respuesta `200`

```json
[
  {
    "event_type": "chat.member.invited",
    "type": "event",
    "severity": "info",
    "description": "Te invitaron a un chat.",
    "default_channels": ["inapp"],
    "available_channels": ["inapp", "email"],
    "is_silenceable": true,
    "channels": {
      "inapp": true,
      "email": false
    }
  },
  {
    "event_type": "auth.password.changed",
    "type": "system",
    "severity": "critical",
    "description": "Cambio de contrasena exitoso.",
    "default_channels": ["inapp", "email"],
    "available_channels": ["inapp", "email"],
    "is_silenceable": false,
    "channels": {
      "inapp": true,
      "email": true
    }
  }
]
```

El campo `channels` muestra el estado **efectivo**: si el usuario tiene un override guardado, se muestra ese valor; si no, el valor por defecto del evento. Los eventos con `is_silenceable: false` siempre se entregan independientemente de las preferencias del usuario.

---

## `PUT /api/v1/me/notification-preferences/event-types/{event_type}/`

**Permiso:** `NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT`

Guarda un override de canal para un tipo de evento específico del usuario autenticado.

`{event_type}` es el string exacto del tipo de evento (p. ej. `chat.member.invited`).

### Request body

```json
{
  "inapp_enabled": true,
  "email_enabled": false
}
```

Al menos uno de los dos campos es requerido. Los no enviados no se modifican.

### Respuesta `200`

El objeto del evento con los `channels` recalculados según el override guardado:

```json
{
  "event_type": "chat.member.invited",
  "type": "event",
  "severity": "info",
  "description": "Te invitaron a un chat.",
  "default_channels": ["inapp"],
  "available_channels": ["inapp", "email"],
  "is_silenceable": true,
  "channels": {
    "inapp": true,
    "email": false
  }
}
```

**Errores:**

| Status | `error` | Causa |
| ------ | ------- | ----- |
| 400 | `bad_request` | Ningún campo enviado |
| 404 | `event_type_not_found` | El `event_type` no existe en el registro |

---

## Relación entre preferencias globales y overrides por evento

El servicio evalúa en este orden al momento de despachar una notificación:

1. Si el evento **no es silenciable** (`is_silenceable: false`): se entrega siempre, sin consultar preferencias.
2. Si el usuario tiene **mute activo** (`mute_until` en el futuro): se suprime.
3. Si el **canal global está deshabilitado** (`inapp_enabled: false` o `email_enabled: false`): se suprime para ese canal.
4. Si existe un **override por evento**: se usa ese valor (`enabled: true/false`).
5. Si no hay override: se usa el **default del evento** (`default_channels`).
