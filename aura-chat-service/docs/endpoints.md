# Catálogo de endpoints REST

Base: **`/api/v1/`** (salvo indicación contraria). Sustituye:

- `{chat_id}` / `{pk}` — id numérico del **chat**.
- `{message_id}` — id del mensaje (`ArtifactMessage.id`, campo **`id`** en el listado; no usar `artifact_id` en la URL).
- `{artifact_id}` — id de la cabecera **artifact** (feedback, bookmark, pin, thread).
- `{member_id}`, `{link_id}`, `{report_id}`, etc. — ids numéricos del recurso.
- `{token}` — UUID del enlace de compartición pública.

Salvo rutas explícitas (health, schema/docs, share público), se asume **`Authorization: Bearer <JWT>`** y permisos de aplicación en el usuario.

---

## Health

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/health` | N/A (`AllowAny`) | Alias de readiness: comprueba PostgreSQL y Redis; `200` si todo OK, `503` si alguna dependencia falla. |
| `GET /api/v1/health/live` | N/A (`AllowAny`) | Liveness: `200` mientras el proceso responde (sin I/O a dependencias). |
| `GET /api/v1/health/ready` | N/A (`AllowAny`) | Readiness: `200`/`503` según DB + Redis. |
| `GET /api/v1/health/startup` | N/A (`AllowAny`) | Startup: mismos checks que readiness; gatea liveness/readiness en el arranque. |

---

## Chats

Prefijo: **`/api/v1/chats/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/chats/` | `LIST_CHATS` | Lista chats del usuario (paginado; `search`, `ordering`, `tags`). |
| `POST /api/v1/chats/` | `CREATE_CHAT` | Crea chat (+ membresía owner). |
| `GET /api/v1/chats/{chat_id}/` | `GET_CHAT` | Detalle del chat. |
| `PATCH /api/v1/chats/{chat_id}/` | `UPDATE_CHAT` | Actualiza metadatos (owner/creador). |
| `DELETE /api/v1/chats/{chat_id}/` | `DELETE_CHAT` | Borrado lógico del chat. |
| `POST /api/v1/chats/delete/` | `DELETE_CHAT` | Borrado lógico masivo por ids en el cuerpo. |
| `GET /api/v1/chats/me/` | `LIST_MY_CHATS` | Chats creados por el usuario. |
| `GET /api/v1/chats/manage/` | `MANAGE_CHATS` | Todos los chats (admin). |
| `GET /api/v1/chats/archived/` | `LIST_ARCHIVED_CHATS` | Chats archivados por el usuario. |
| `POST /api/v1/chats/archive/` | `ARCHIVE_CHAT` | Archiva chats por ids en cuerpo. |
| `POST /api/v1/chats/unarchive/` | `UNARCHIVE_CHAT` | Desarchiva chats. |
| `POST /api/v1/chats/{chat_id}/pin/` | `PIN_CHAT` | Fija chat en el listado del usuario. |
| `DELETE /api/v1/chats/{chat_id}/pin/` | `PIN_CHAT` | Quita pin. |
| `POST /api/v1/chats/{chat_id}/lock/` | `LOCK_CHAT` | Bloquea envío de mensajes. |
| `DELETE /api/v1/chats/{chat_id}/lock/` | `LOCK_CHAT` | Desbloquea. |
| `DELETE /api/v1/chats/{chat_id}/clear/` | `CLEAR_CHAT_HISTORY` | Borra suavemente todos los artifacts del chat (owner). |
| `POST /api/v1/chats/{chat_id}/read/` | `MARK_CHAT_AS_READ` | Marca leído (membresía). |
| `POST /api/v1/chats/{chat_id}/transcribe/` | `SEND_MESSAGE` | Transcribe audio multipart; requiere membresía activa y chat no bloqueado. |
| `GET /api/v1/chats/{chat_id}/export/pdf/` | `EXPORT_CHAT` | PDF del historial. |
| `GET /api/v1/chats/{chat_id}/export/markdown/` | `EXPORT_CHAT` | Markdown del historial. |
| `GET /api/v1/chats/{chat_id}/manage/export/pdf/` | `MANAGE_CHATS` | Export admin PDF. |
| `GET /api/v1/chats/{chat_id}/manage/export/markdown/` | `MANAGE_CHATS` | Export admin Markdown. |

### Share links (autenticado)

Prefijo: **`/api/v1/chats/{chat_id}/share-links/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET .../share-links/` | `LIST_SHARE_LINKS` | Lista enlaces (solo creador del chat). |
| `POST .../share-links/` | `CREATE_SHARE_LINK` | Crea enlace (`expires_at` opcional). |
| `DELETE .../share-links/{link_id}/` | `DELETE_SHARE_LINK` | Revoca enlace. |

---

## Mensajes (REST)

Prefijo: **`/api/v1/messages/`** — el chat se indica con **`?chat_id=`** en los listados (no cuelga de `/chats/{id}/`).

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/messages/?chat_id=` | `LIST_MESSAGES` | Historial del chat con paginación **cursor** (orden `-id`); anotaciones bookmark/feedback/thread. Requiere membresía activa. |
| `POST /api/v1/messages/generate/` | `SEND_MESSAGE` | Envía texto o audio (multipart), persiste el mensaje del usuario y ejecuta la respuesta IA (modo opcional). `409` si ya hay una respuesta IA en curso. |
| `GET /api/v1/messages/manage/?chat_id=` | `MANAGE_MESSAGES` | Historial admin sin exigir membresía. |
| `GET /api/v1/messages/{message_id}/` | `GET_MESSAGE` | Detalle de un mensaje (`message_id` = campo **`id`**). |
| `DELETE /api/v1/messages/{message_id}/` | `DELETE_MESSAGE` | Borrado lógico (solo el dueño del chat). |
| `GET /api/v1/messages/{message_id}/export/pdf/` | `EXPORT_MESSAGE` | PDF de un mensaje. |
| `GET /api/v1/messages/{message_id}/export/markdown/` | `EXPORT_MESSAGE` | Markdown de un mensaje. |
| `GET /api/v1/messages/manage/{message_id}/export/pdf\|markdown/` | `MANAGE_EXPORT_MESSAGE` | Export admin de un mensaje. |

**Tiempo real:** envío y streaming IA vía **WebSocket** (ver `docs/websockets.md`), no sustituye a `generate/` REST.

---

## Mensajes entre personas (peer messages)

Prefijo: **`/api/v1/chats/{chat_id}/peer-messages/`** — canal directo persona↔persona dentro del chat, separado de la conversación con IA (`artifact_message`). Gated por **membresía activa** (sin constante de permiso dedicada).

| Método y ruta | Qué hace |
|---------------|----------|
| `GET .../peer-messages/` | Lista los mensajes entre personas del chat. |
| `POST .../peer-messages/` | Envía un mensaje. |
| `GET .../peer-messages/{message_id}/` | Detalle. |
| `PATCH .../peer-messages/{message_id}/` | Edita (autor). |
| `DELETE .../peer-messages/{message_id}/` | Borra (autor). |

---

## Artifacts (interacciones)

Prefijo: **`/api/v1/artifacts/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/artifacts/chats/{chat_id}/` | miembro activo | Feed de artifacts del chat (`type`, `created_by`, `date_from`, `date_to`). |
| `GET /api/v1/artifacts/chats/{chat_id}/manage/` | `MANAGE_CHAT_ARTIFACTS` | Feed admin sin requerir membresía. |
| `GET /api/v1/artifacts/{artifact_id}/` | `GET_ARTIFACT` | Detalle cabecera artifact. |
| `DELETE /api/v1/artifacts/{artifact_id}/` | `DELETE_ARTIFACT` | Borrado lógico (creador o owner/editor del chat). |
| `POST /api/v1/artifacts/{artifact_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Pulgar arriba/abajo (solo respuestas IA). |
| `DELETE /api/v1/artifacts/{artifact_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Quita feedback. |
| `POST /api/v1/artifacts/{artifact_id}/bookmark/` | `BOOKMARK_MESSAGE` | Marca artifact. |
| `DELETE /api/v1/artifacts/{artifact_id}/bookmark/` | `BOOKMARK_MESSAGE` | Quita marcador. |
| `POST /api/v1/artifacts/{artifact_id}/pin/` | `PIN_MESSAGE` | Fija en el chat. |
| `DELETE /api/v1/artifacts/{artifact_id}/pin/` | `PIN_MESSAGE` | Desfija. |
| `GET /api/v1/artifacts/{artifact_id}/thread/` | `LIST_THREAD_REPLIES` | Lista replies del hilo. |
| `POST /api/v1/artifacts/{artifact_id}/thread/` | `ADD_THREAD_REPLY` | Añade reply. |
| `PATCH /api/v1/artifacts/{artifact_id}/thread/{reply_id}/` | `EDIT_THREAD_REPLY` | Edita reply del hilo (autor). |
| `DELETE /api/v1/artifacts/{artifact_id}/thread/{reply_id}/` | `DELETE_THREAD_REPLY` | Elimina reply del hilo (autor). |
| `GET /api/v1/artifacts/pinned/?chat_id=` | `LIST_PINNED_MESSAGES` | Lista fijados del chat (query `chat_id` obligatorio). |
| `GET /api/v1/artifacts/bookmarked/?chat_id=` | `LIST_BOOKMARKS` | Lista marcados del usuario en el chat (`chat_id` obligatorio). |
| `GET /api/v1/artifacts/feedback/analytics/` | `VIEW_FEEDBACK_ANALYTICS` | Dashboard admin de feedback. |

---

## Informes, checklists y otros artifacts tipados

Cada tipo sigue el mismo patrón bajo su prefijo:

- **`/api/v1/reports/`** — SITREP, INTSUM, OPORD (`LLM_REPORT_GENERATE_URL`)
- **`/api/v1/checklists/`** — checklists (`LLM_CHECKLIST_GENERATE_URL`)
- **`/api/v1/timelines/`** — líneas de tiempo (`LLM_TIMELINE_GENERATE_URL`)
- **`/api/v1/quizzes/`** — cuestionarios (`LLM_QUIZ_GENERATE_URL`)
- **`/api/v1/lessons-learned/`** — lecciones aprendidas (`LLM_LESSONS_LEARNED_GENERATE_URL`)
- **`/api/v1/decision-briefs/`** — briefs de decisión (`LLM_DECISION_BRIEF_GENERATE_URL`)
- **`/api/v1/document-summaries/`** — resúmenes de documentos (`LLM_DOCUMENT_SUMMARY_URL`)
- **`/api/v1/document-actions/`** — acciones sobre documentos (`LLM_DOCUMENT_ACTION_URL`)

Por prefijo, en general:

| Rutas típicas | Permisos | Notas |
|---------------|----------|-------|
| `GET /` | `LIST_*` | Lista del usuario; filtro `chat_id` opcional. |
| `GET /manage/` | `MANAGE_*` | Lista admin. |
| `POST /generate/` | `LLM_*_GENERATE` | Generación IA. Los tipos de documento (summary/action) reciben `document_ids`; el resto usa el chat/mensaje. |
| `GET /{id}/` | `GET_*` | Detalle del cuerpo tipado. |
| `DELETE /{id}/` | `DELETE_*` | Borrado lógico. |
| `GET /{id}/export/pdf\|markdown/` | `EXPORT_*` | Descarga. |
| `GET /manage/{id}/export/pdf\|markdown/` | `MANAGE_EXPORT_*` | Export admin. |

**No hay un `PATCH /{id}/` genérico del cuerpo.** Solo hay edición vía sub-recursos específicos:

- **Checklists:** `PATCH /api/v1/checklists/{id}/items/{item_id}/` (`UPDATE_CHECKLIST`) para marcar/actualizar un ítem.
- **Quizzes:** `POST /api/v1/quizzes/{id}/questions/{question_id}/answer/` y `POST /api/v1/quizzes/{id}/reset/` (`UPDATE_QUIZ`).

El resto de tipos son solo `GET` / `DELETE` / export.

Si la variable de entorno del endpoint LLM correspondiente está vacía, la API responde **502/503** con error de servicio LLM no configurado (no intenta llamar a URL vacía).

---

## Asistentes

Prefijo: **`/api/v1/assistants/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /` | `LIST_ASSISTANTS` | Asistentes activos. |
| `POST /` | `CREATE_ASSISTANT` | Crea asistente. |
| `GET /manage/` | `MANAGE_ASSISTANTS` | Todos (admin). |
| `GET|PATCH|DELETE /{assistant_id}/` | `GET/UPDATE/DELETE_ASSISTANT` | CRUD. |
| `POST /{assistant_id}/start-chat/` | `USE_ASSISTANT` | Crea o reanuda chat ligado al asistente. |

---

## Membresías

Prefijo: **`/api/v1/chats/{chat_id}/members/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET .../members/` | `LIST_MEMBERS` | Miembros del chat (`status` query). |
| `GET .../members/manage/` | `MANAGE_MEMBERS` | Lista admin. |
| `POST .../members/` | `ADD_MEMBER` | Invita usuarios (pending). |
| `PATCH .../members/{member_id}/` | `UPDATE_MEMBER` | El invitado acepta/rechaza (`active`/`inactive`). |
| `DELETE .../members/{member_id}/` | `REMOVE_MEMBER` | Expulsión (owner). |
| `PATCH .../members/{member_id}/role/` | `UPDATE_MEMBER_ROLE` | Cambia rol. |
| `POST .../members/leave/` | `LEAVE_CHAT` | Abandona el chat. |

Prefijo global: **`/api/v1/memberships/me/`** — membresías del usuario autenticado (`LIST_MY_MEMBERSHIPS`).

---

## Share público (solo lectura)

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/share/{token}/messages/` | N/A (`AllowAny`) | Historial paginado vía token; sin Bearer. |

---

## Documentación OpenAPI

- Esquema: `GET /api/schema/`
- Swagger: `GET /api/docs/`
- ReDoc: `GET /api/redoc/`

Para cuerpos, códigos de error y query params exactos, usar OpenAPI o `docs/errors-and-status-codes.md`.
