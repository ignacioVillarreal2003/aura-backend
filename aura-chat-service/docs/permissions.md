# Permisos (constantes)

Las cadenas son **identificadores lógicos** enviados por el servicio de autenticación/autorización junto al usuario. El chat service **no** define matriz usuario→permiso: solo verifica que el conjunto del usuario contenga los requeridos para la operación.

Referencia de rutas que usan cada permiso: [endpoints.md](endpoints.md).

## Chats

| Constante | Ámbito |
|-----------|--------|
| `LIST_CHATS` | Listar chats accesibles al usuario (bandeja principal). |
| `LIST_MY_CHATS` | Listar chats creados por el usuario. |
| `LIST_ARCHIVED_CHATS` | Listar chats archivados. |
| `CREATE_CHAT` | Crear chat. |
| `GET_CHAT` | Leer detalle de un chat. |
| `UPDATE_CHAT` | Actualizar metadatos del chat. |
| `DELETE_CHAT` | Eliminar chat. |
| `PIN_CHAT` | Fijar o desfijar chat en la lista (orden personal). |
| `ARCHIVE_CHAT` | Archivar uno o más chats (bulk). |
| `UNARCHIVE_CHAT` | Restaurar chats archivados (bulk). |
| `LOCK_CHAT` | Bloquear o desbloquear envío de mensajes en el chat. |

## Share links

| Constante | Ámbito |
|-----------|--------|
| `LIST_SHARE_LINKS` | Ver enlaces de compartición del chat. |
| `CREATE_SHARE_LINK` | Crear enlace de solo lectura con token. |
| `DELETE_SHARE_LINK` | Revocar enlace. |

## Webhooks

| Constante | Ámbito |
|-----------|--------|
| `LIST_WEBHOOKS` | Listar webhooks del chat. |
| `CREATE_WEBHOOK` | Crear suscripción HTTP saliente. |
| `UPDATE_WEBHOOK` | Modificar webhook existente. |
| `DELETE_WEBHOOK` | Eliminar webhook. |

## Miembros

| Constante | Ámbito |
|-----------|--------|
| `LIST_MEMBERS` | Listar miembros del chat. |
| `ADD_MEMBER` | Invitar / añadir miembros. |
| `UPDATE_MEMBER` | Cambiar estado de membresía. |
| `REMOVE_MEMBER` | Eliminar a otro miembro. |
| `LEAVE_CHAT` | Abandonar el chat (propio). |
| `UPDATE_MEMBER_ROLE` | Cambiar rol de un miembro. |

## Mensajes

| Constante | Ámbito |
|-----------|--------|
| `LIST_MESSAGES` | Listar mensajes del chat. |
| `SEND_MESSAGE` | Enviar mensaje (texto/audio) y flujos asociados. |
| `DELETE_MESSAGE` | Borrar un mensaje. |
| `CLEAR_CHAT_HISTORY` | Vaciar historial según reglas de negocio. |
| `MARK_CHAT_AS_READ` | Marcar lectura / cursor de leído. |
| `REGENERATE_AI_RESPONSE` | Regenerar última respuesta del asistente. |

## Bookmarks

| Constante | Ámbito |
|-----------|--------|
| `LIST_BOOKMARKS` | Listar mensajes marcados por el usuario. |
| `BOOKMARK_MESSAGE` | Crear o quitar bookmark. |

## Mensajes fijados (pin de mensaje)

| Constante | Ámbito |
|-----------|--------|
| `LIST_PINNED_MESSAGES` | Listar mensajes anclados en el chat. |
| `PIN_MESSAGE` | Fijar o desfijar un mensaje. |

## Feedback

| Constante | Ámbito |
|-----------|--------|
| `SET_MESSAGE_FEEDBACK` | Crear, actualizar o eliminar feedback (pulgar) en mensajes del asistente. |

## Hilos (threads)

| Constante | Ámbito |
|-----------|--------|
| `LIST_THREAD_REPLIES` | Leer respuestas de un hilo. |
| `ADD_THREAD_REPLY` | Añadir respuesta en un hilo. |

## Exportación

| Constante | Ámbito |
|-----------|--------|
| `EXPORT_CHAT` | Exportar chat o mensaje (PDF, MD, JSON, IA-only, PDF de mensaje). |
