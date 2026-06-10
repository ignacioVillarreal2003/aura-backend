# API de preferencias de notificación

Vistas: `apps/notification/api/views/preference_views.py`  
Serializers: `apps/notification/api/serializers/preferences.py`  
Servicio: `apps/notification/services/preference_service.py`

Las preferencias controlan si un usuario recibe notificaciones y por qué canal. Si un usuario nunca configuró preferencias, el servicio opera con los valores por defecto del modelo (in-app habilitado, email habilitado, sin mute).

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
| 400 | `bad_request` | `mute_until` en el pasado o timezone inválida |

---

## Cómo se evalúan las preferencias al despachar

El servicio evalúa en este orden al momento de despachar una notificación:

1. Si el evento **no es silenciable** (`is_silenceable: false`): se entrega siempre, sin consultar preferencias.
2. Si el usuario tiene **mute activo** (`mute_until` en el futuro): se suprime.
3. Si el **canal global está deshabilitado** (`inapp_enabled: false` o `email_enabled: false`): se suprime para ese canal.
4. Si el canal **no está en `default_channels`** del evento: se suprime para ese canal.

Para ver los canales por defecto de cada evento, consultar `GET /api/v1/event-types/`.
