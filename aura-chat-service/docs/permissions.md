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
| `MANAGE_CHATS` | Operaciones admin sobre cualquier chat (listado global, export admin). |

## Share links

| Constante | Ámbito |
|-----------|--------|
| `LIST_SHARE_LINKS` | Ver enlaces de compartición del chat. |
| `CREATE_SHARE_LINK` | Crear enlace de solo lectura con token. |
| `DELETE_SHARE_LINK` | Revocar enlace. |

## Miembros

| Constante | Ámbito |
|-----------|--------|
| `LIST_MEMBERS` | Listar miembros del chat. |
| `ADD_MEMBER` | Invitar / añadir miembros. |
| `UPDATE_MEMBER` | Cambiar estado de membresía. |
| `REMOVE_MEMBER` | Eliminar a otro miembro. |
| `LEAVE_CHAT` | Abandonar el chat (propio). |
| `UPDATE_MEMBER_ROLE` | Cambiar rol de un miembro. |
| `LIST_MY_MEMBERSHIPS` | Listar las membresías del propio usuario. |
| `MANAGE_MEMBERS` | Listado/gestión admin de miembros. |

## Mensajes

| Constante | Ámbito |
|-----------|--------|
| `LIST_MESSAGES` | Listar mensajes del chat. |
| `GET_MESSAGE` | Leer el detalle de un mensaje. |
| `SEND_MESSAGE` | Enviar mensaje (texto/audio) y flujos asociados. |
| `DELETE_MESSAGE` | Borrar un mensaje. |
| `EXPORT_MESSAGE` | Exportar un mensaje individual (PDF / Markdown). |
| `MANAGE_MESSAGES` | Listado admin de mensajes sin requerir membresía. |
| `MANAGE_EXPORT_MESSAGE` | Export admin de un mensaje. |
| `CLEAR_CHAT_HISTORY` | Vaciar historial según reglas de negocio. |
| `MARK_CHAT_AS_READ` | Marcar lectura / cursor de leído. |

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
| `VIEW_FEEDBACK_ANALYTICS` | Ver el dashboard admin de analytics de feedback. |

## Hilos (threads)

| Constante | Ámbito |
|-----------|--------|
| `LIST_THREAD_REPLIES` | Leer respuestas de un hilo. |
| `ADD_THREAD_REPLY` | Añadir respuesta en un hilo. |
| `EDIT_THREAD_REPLY` | Editar la propia respuesta de un hilo. |
| `DELETE_THREAD_REPLY` | Eliminar la propia respuesta de un hilo. |

## Artifacts (cabecera)

| Constante | Ámbito |
|-----------|--------|
| `LIST_ARTIFACTS` | Listar artifacts. |
| `GET_ARTIFACT` | Leer el detalle de un artifact. |
| `DELETE_ARTIFACT` | Borrado lógico de un artifact. |
| `MANAGE_ARTIFACTS` | Gestión admin de artifacts. |
| `MANAGE_CHAT_ARTIFACTS` | Feed admin de artifacts de un chat sin requerir membresía. |

## Asistentes

| Constante | Ámbito |
|-----------|--------|
| `LIST_ASSISTANTS` / `GET_ASSISTANT` | Listar / leer asistentes disponibles. |
| `USE_ASSISTANT` | Iniciar o reanudar un chat ligado a un asistente. |
| `CREATE_ASSISTANT` / `UPDATE_ASSISTANT` / `DELETE_ASSISTANT` | CRUD admin de asistentes. |
| `MANAGE_ASSISTANTS` | Listado admin de todos los asistentes. |

## Artifacts tipados (informes, checklists, timelines, quizzes, lessons learned, decision briefs, document summaries/actions)

Cada tipo `X` (report, checklist, timeline, quiz, lessons_learned, decision_brief, document_summary, document_action) define la misma familia de constantes:

| Patrón | Ámbito |
|--------|--------|
| `LIST_<X>` | Listar los del usuario. |
| `GET_<X>` | Leer el detalle. |
| `DELETE_<X>` | Borrado lógico. |
| `EXPORT_<X>` | Exportar (PDF / Markdown). |
| `MANAGE_<X>` | Listado admin. |
| `MANAGE_EXPORT_<X>` | Export admin. |
| `LLM_<X>_GENERATE` | Generar el artifact con IA. |

Además, edición de sub-recursos: `UPDATE_CHECKLIST` (marcar ítems) y `UPDATE_QUIZ` (responder / reset). No existen `UPDATE_*` para el resto de tipos.

## Exportación

| Constante | Ámbito |
|-----------|--------|
| `EXPORT_CHAT` | Exportar el historial completo del chat (PDF / Markdown). |
