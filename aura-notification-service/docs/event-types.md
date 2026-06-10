# Catálogo de tipos de evento

Fuente de verdad: `apps/notification/events/registry.py` — clase `EventDefinition` y diccionario `_EVENTS`.  
El mismo catálogo se expone en vivo sin autenticación en `GET /api/v1/event-types/`.

---

## Campos de una definición de evento

| Campo | Tipo | Descripción |
| ----- | ---- | ----------- |
| `event_type` | `str` | Identificador único. Formato `dominio.entidad.accion` (p. ej. `chat.member.invited`). |
| `type` | `str` | Categoría de la notificación: `event`, `system`, `admin`, `user`. |
| `severity` | `str` | Gravedad visual: `info`, `success`, `warning`, `critical`. |
| `description` | `str` | Texto fijo que se persiste en el campo `message` de la notificación. |
| `default_channels` | `tuple[str]` | Canales activos por defecto si el usuario no tiene overrides. Valores: `inapp`, `email`. |
| `available_channels` | `tuple[str]` | Canales que el usuario puede configurar. Todos los eventos actuales permiten `inapp` y `email`. |
| `is_silenceable` | `bool` | Si es `false`, el evento se entrega siempre ignorando mute y overrides de canal. Default: `true`. |
| `template_id` | `str` | ID interno que el worker de Celery usa para renderizar el cuerpo del email. No se expone en la API. |
| `link_builder` | `callable` | Función que recibe el `context` del request y devuelve una URL o `None`. Determina el campo `link_url` de la notificación. |

---

## Eventos registrados

### Chat

| `event_type` | `type` | `severity` | `default_channels` | `is_silenceable` | Link (campo de `context`) |
| ------------ | ------ | ---------- | ------------------ | ---------------- | ------------------------- |
| `chat.member.invited` | `event` | `info` | `inapp` | `true` | `chat_id` → `/chats/{chat_id}` |
| `chat.member.removed` | `event` | `warning` | `inapp` | `true` | `chat_id` → `/chats/{chat_id}` |
| `chat.locked` | `event` | `warning` | `inapp` | `true` | `chat_id` → `/chats/{chat_id}` |

Los tres eventos de chat construyen el `link_url` a partir de `context.chat_id`:

```
{NOTIFICATION_DEFAULT_LINK_BASE_URL}/chats/{chat_id}
```

Si `chat_id` no viene en `context`, `link_url` queda en `null`.

---

### Autenticación

| `event_type` | `type` | `severity` | `default_channels` | `is_silenceable` | Link |
| ------------ | ------ | ---------- | ------------------ | ---------------- | ---- |
| `auth.password.changed` | `system` | `critical` | `inapp` + `email` | **`false`** | ninguno |
| `auth.new_login` | `system` | `warning` | `inapp` + `email` | `true` | ninguno |

`auth.password.changed` es **no silenciable**: se entrega siempre, sin importar mute ni preferencias de canal del usuario.

---

### Documentos

| `event_type` | `type` | `severity` | `default_channels` | `is_silenceable` | Link (campo de `context`) |
| ------------ | ------ | ---------- | ------------------ | ---------------- | ------------------------- |
| `document.processing.done` | `event` | `success` | `inapp` | `true` | `document_id` → `/documents/{document_id}` |
| `document.processing.failed` | `event` | `critical` | `inapp` + `email` | `true` | `document_id` → `/documents/{document_id}` |

El link se construye a partir de `context.document_id`:

```
{NOTIFICATION_DEFAULT_LINK_BASE_URL}/documents/{document_id}
```

---

### Admin y sistema

| `event_type` | `type` | `severity` | `default_channels` | `is_silenceable` | Link |
| ------------ | ------ | ---------- | ------------------ | ---------------- | ---- |
| `admin.broadcast` | `admin` | `info` | `inapp` | `true` | ninguno |
| `system.announcement` | `system` | `info` | `inapp` | **`false`** | ninguno |

`system.announcement` es **no silenciable**, igual que `auth.password.changed`.

---

## Resumen: cuándo se envía email por defecto

| `event_type` | Email por defecto |
| ------------ | ----------------- |
| `chat.*` | No |
| `auth.password.changed` | Sí (forzado, no silenciable) |
| `auth.new_login` | Sí (salvo override del usuario) |
| `document.processing.done` | No |
| `document.processing.failed` | Sí (salvo override del usuario) |
| `admin.broadcast` | No |
| `system.announcement` | No (pero siempre llega in-app, no silenciable) |

---

## Cómo agregar un nuevo tipo de evento

1. Agregar la constante en `EventType` dentro de `registry.py`.
2. Registrar la `EventDefinition` en el diccionario `_EVENTS` con todos sus campos.
3. Si necesita un link, agregar o reutilizar un `link_builder` (función `_xxx_link`).
4. Crear la plantilla de email correspondiente con el `template_id` elegido.
5. El nuevo evento queda disponible automáticamente en `GET /api/v1/event-types/` y puede recibirse via `POST /api/v1/internal/events/`.

No hace falta migración de base de datos: los event types son definiciones en código, no filas en la DB.
