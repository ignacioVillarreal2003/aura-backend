# Catálogo de endpoints REST

Base: **`/api/v1/`** (salvo indicación contraria). Sustituye:

- `{pk}` — id numérico del **chat** (clave primaria).
- `{chat_id}` — mismo criterio en rutas anidadas.
- `{message_id}`, `{member_id}`, `{link_id}`, `{webhook_id}` — ids numéricos.
- `{token}` — UUID del enlace de compartición pública.

Salvo rutas explícitas como health, documentación o share público, se asume **`Authorization: Bearer <JWT>`** y usuario con los permisos indicados.

---

## Health

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET /api/v1/health` | N/A (`AllowAny`) | Comprueba conectividad a PostgreSQL y Redis; devuelve `status` y `checks` por dependencia. | **Liveness/readiness** en orquestadores, balanceadores y monitoreo. |

---

## Chats

Prefijo: **`/api/v1/chats/`**

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET /api/v1/chats/` | `LIST_CHATS` | Lista chats visibles para el usuario con filtros (`search`, `ordering`, `tags`). Paginación por página. | **Bandeja principal** de conversaciones. |
| `POST /api/v1/chats/` | `CREATE_CHAT` | Crea un chat (nombre, prompts opcionales, tags, flags efímero/bloqueo según payload). | **Iniciar conversación** nueva. |
| `GET /api/v1/chats/{pk}/` | `GET_CHAT` | Obtiene detalle de un chat por id. | **Ficha** del chat; cabecera de UI. |
| `PATCH /api/v1/chats/{pk}/` | `UPDATE_CHAT` | Actualiza metadatos del chat (nombre, prompts, estilo, tags, etc.). | **Editar configuración** del hilo. |
| `DELETE /api/v1/chats/{pk}/` | `DELETE_CHAT` | Elimina el chat (lógica de borrado según servicio). | **Borrar** conversación. |
| `GET /api/v1/chats/me/` | `LIST_MY_CHATS` | Lista chats **creados por** el usuario actual, con los mismos filtros opcionales que el listado global. | Vista **“mis chats”** / creados por mí. |
| `GET /api/v1/chats/archived/` | `LIST_ARCHIVED_CHATS` | Lista chats **archivados** para el usuario. | Bandeja de **archivados**. |
| `POST /api/v1/chats/archive/` | `ARCHIVE_CHAT` | Archiva uno o varios chats por ids en el cuerpo (`BulkChatIdsRequest`). Devuelve recuento archivados. | **Archivar en bloque** desde la UI. |
| `POST /api/v1/chats/unarchive/` | `UNARCHIVE_CHAT` | Restaura uno o varios chats archivados. | **Desarchivar en bloque**. |
| `POST /api/v1/chats/{pk}/pin/` | `PIN_CHAT` | Fija el chat en la parte superior del listado (ámbito usuario). | **Destacar** conversación. |
| `DELETE /api/v1/chats/{pk}/pin/` | `PIN_CHAT` | Quita el fijado del chat. | Quitar **pin**. |
| `POST /api/v1/chats/{pk}/lock/` | `LOCK_CHAT` | Bloquea el chat para que **no se envíen mensajes** (control de moderación). | **Modo solo lectura** forzado (p. ej. owner). |
| `DELETE /api/v1/chats/{pk}/lock/` | `LOCK_CHAT` | Desbloquea el chat. | Restaurar envío de mensajes. |
| `POST /api/v1/chats/{pk}/mute/` | `MUTE_CHAT` | Silencia notificaciones o el chat hasta una fecha (`muted_until` en cuerpo). | **Silenciar** hasta… |
| `DELETE /api/v1/chats/{pk}/mute/` | `MUTE_CHAT` | Quita el silencio. | **Dejar de silenciar**. |

---

## Share links (autenticado)

Prefijo: **`/api/v1/chats/{chat_id}/share-links/`**

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET .../share-links/` | `LIST_SHARE_LINKS` | Lista enlaces de lectura compartida del chat (paginado). | **Auditar** o gestionar enlaces existentes. |
| `POST .../share-links/` | `CREATE_SHARE_LINK` | Crea un enlace (opcional `expires_at`). | **Compartir historial** de solo lectura con un token. |
| `DELETE .../share-links/{link_id}/` | `DELETE_SHARE_LINK` | Revoca un enlace concreto. | **Invalidar** un share link. |

---

## Webhooks

Prefijo: **`/api/v1/chats/{chat_id}/webhooks/`**

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET .../webhooks/` | `LIST_WEBHOOKS` | Lista webhooks configurados para notificar eventos externos (paginado). | **Inspección** de integraciones salientes. |
| `POST .../webhooks/` | `CREATE_WEBHOOK` | Registra URL, eventos y secreto para firmar llamadas. | **Integrar** sistemas externos (mensajes, miembros, lock…). |
| `PATCH .../webhooks/{webhook_id}/` | `UPDATE_WEBHOOK` | Actualiza URL, eventos, secreto o estado. | **Cambiar endpoint** o rotar secreto. |
| `DELETE .../webhooks/{webhook_id}/` | `DELETE_WEBHOOK` | Elimina el webhook. | **Dar de baja** la integración. |

---

## Mensajes (REST)

Prefijo: **`/api/v1/chats/{chat_id}/messages/`**

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET .../messages/` | `LIST_MESSAGES` | Lista mensajes del chat con paginación **cursor** y anotaciones (bookmark, feedback del usuario, conteo de replies). | **Historial** y scroll infinito. |
| `POST .../messages/` | `SEND_MESSAGE` | Envía texto y/o audio; dispara transcripción o flujo LLM según payload (comportamiento asíncrono vía servicio; detalle en OpenAPI). | **Enviar mensaje** de usuario o disparar voz→texto. |
| `POST .../messages/clear/` | `CLEAR_CHAT_HISTORY` | Borra o trunca el historial según la lógica del servicio. | **Limpiar conversación**. |
| `POST .../messages/read/` | `MARK_CHAT_AS_READ` | Marca el chat como leído hasta un punto (actualiza membresía / última lectura). | Sincronizar **estado leído** / badge. |
| `GET .../messages/pinned/` | `LIST_PINNED_MESSAGES` | Lista mensajes **anclados** del chat (paginado). | Panel de **destacados**. |
| `POST .../messages/regenerate/` | `REGENERATE_AI_RESPONSE` | Elimina la última respuesta del asistente y vuelve a solicitar generación (LLM); respuesta JSON con `assistant` / `assistant_error`. | **Regenerar** última respuesta IA. |
| `GET .../messages/bookmarked/` | `LIST_BOOKMARKS` | Lista mensajes marcados como favoritos por el usuario en ese chat (paginado con cursor). | Vista de **guardados**. |
| `GET .../messages/export/pdf/` | `EXPORT_CHAT` | Descarga PDF del historial completo del chat. | **Exportación** para archivo / compliance. |
| `GET .../messages/export/markdown/` | `EXPORT_CHAT` | Descarga Markdown del historial. | Export para **docs** o edición. |
| `GET .../messages/export/json/` | `EXPORT_CHAT` | Descarga backup JSON del chat. | **Backup** estructurado. |
| `GET .../messages/export/ai/` | `EXPORT_CHAT` | Descarga solo respuestas del modelo en Markdown. | **Resumen de IA**. |
| `DELETE .../messages/{message_id}/` | `DELETE_MESSAGE` | Elimina un mensaje concreto (reglas de negocio en servicio). | **Moderación** o corrección. |
| `POST .../messages/{message_id}/bookmark/` | `BOOKMARK_MESSAGE` | Añade bookmark al mensaje para el usuario. | **Guardar** mensaje. |
| `DELETE .../messages/{message_id}/bookmark/` | `BOOKMARK_MESSAGE` | Quita bookmark. | Quitar de guardados. |
| `POST .../messages/{message_id}/pin/` | `PIN_MESSAGE` | Fija un mensaje en el chat (ancla conversacional). | **Fijar** mensaje importante. |
| `DELETE .../messages/{message_id}/pin/` | `PIN_MESSAGE` | Elimina el pin del mensaje. | Quitar ancla. |
| `GET .../messages/{message_id}/thread/` | `LIST_THREAD_REPLIES` | Lista respuestas de hilo ligadas al mensaje padre. | Mostrar **sub-hilo** (thread). |
| `POST .../messages/{message_id}/thread/` | `ADD_THREAD_REPLY` | Añade una respuesta en el hilo. | **Responder en hilo**. |
| `POST .../messages/{message_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Envía valor 1 / -1 (pulgar arriba/abajo) para un mensaje del **asistente**. | **Valoración** de respuesta IA. |
| `DELETE .../messages/{message_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Elimina la valoración del usuario sobre ese mensaje. | **Retirar** feedback. |
| `GET .../messages/{message_id}/export/pdf/` | `EXPORT_CHAT` | Descarga PDF de un **solo** mensaje en contexto. | Export puntual. |

---

## Membresías

Prefijo: **`/api/v1/chats/{chat_id}/members/`**

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET .../members/` | `LIST_MEMBERS` | Lista miembros del chat; query `status` (p. ej. active, all). Paginado. | **Ver participantes** / roles en UI. |
| `POST .../members/` | `ADD_MEMBER` | Invita usuarios por lista de ids (opcional uso de token en cabecera para downstream). | **Añadir gente** al chat. |
| `PATCH .../members/{member_id}/` | `UPDATE_MEMBER` | Cambia el **estado** de membresía (transiciones validadas en servicio). | Aprobar, desactivar, etc. |
| `DELETE .../members/{member_id}/` | `REMOVE_MEMBER` | Expulsa o elimina a un miembro (reglas de rol). | **Quitar usuario** del chat. |
| `PATCH .../members/{member_id}/role/` | `UPDATE_MEMBER_ROLE` | Actualiza el **rol** (owner/editor/reader según modelo). | **Gestión de permisos** finos en el hilo. |
| `POST .../members/leave/` | `LEAVE_CHAT` | Abandona el chat el usuario autenticado. | Botón **“Salir del grupo”**. |

---

## Share público (solo lectura)

Sin **Bearer** de aplicación en rutas bajo `/api/v1/share/` (según exclusión de autenticación en settings).

| Método y ruta | Permiso | Qué hace | Para qué se usa |
|---------------|---------|----------|-----------------|
| `GET /api/v1/share/{token}/messages/` | N/A (`AllowAny`) | Lista mensajes visibles a través del token de share (paginado); validez y expiración según servicio de enlaces. | **Vista pública** de solo lectura sin cuenta en este servicio. |

---

## Resumen de prerequisitos

Además del **permiso** string, muchos endpoints comprueban **membresía activa** en `{chat_id}` o existencia del mensaje/miembro. Las respuestas **403** / **404** dependen de la capa de dominio; el listado anterior describe la intención y el permiso mínimo declarado en código.

Para tipos de cuerpo, códigos de error y parámetros query exactos, usar **`GET /api/schema/`** o la UI en **`/api/docs/`**.
