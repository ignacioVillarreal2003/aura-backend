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
| `GET /api/v1/health` | N/A (`AllowAny`) | Comprueba PostgreSQL y Redis; `200` si todo OK, `503` si degradado. |

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

Prefijo: **`/api/v1/chats/{chat_id}/messages/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET .../messages/` | `LIST_MESSAGES` | Historial con paginación **cursor**; anotaciones bookmark/feedback/thread. |
| `POST .../messages/generate/` | `SEND_MESSAGE` | Envía texto o audio, persiste mensaje usuario y ejecuta respuesta IA (modo opcional). |
| `GET .../messages/manage/` | `MANAGE_CHATS` | Historial admin sin exigir membresía. |
| `DELETE .../messages/{message_id}/` | `DELETE_MESSAGE` | Borrado lógico (`message_id` = campo **`id`**). |
| `GET .../messages/{message_id}/export/pdf/` | `EXPORT_CHAT` | PDF de un mensaje. |
| `GET .../messages/{message_id}/export/markdown/` | `EXPORT_CHAT` | Markdown de un mensaje. |
| `GET .../messages/manage/{message_id}/export/...` | `MANAGE_CHATS` | Export admin de un mensaje. |

**Tiempo real:** envío y streaming IA vía **WebSocket** (ver `docs/websockets.md`), no sustituye a `generate/` REST.

---

## Artifacts (interacciones)

Prefijo: **`/api/v1/artifacts/`**

| Método y ruta | Permiso | Qué hace |
|---------------|---------|----------|
| `GET /api/v1/artifacts/` | `LIST_ARTIFACTS` | Lista artifacts del usuario (`type`, `chat_id` query). |
| `GET /api/v1/artifacts/manage/` | `MANAGE_ARTIFACTS` | Lista global admin. |
| `GET /api/v1/artifacts/{artifact_id}/` | `GET_ARTIFACT` | Detalle cabecera artifact. |
| `PATCH /api/v1/artifacts/{artifact_id}/` | `UPDATE_ARTIFACT` | Actualiza título/descripción/estado (versionado). |
| `DELETE /api/v1/artifacts/{artifact_id}/` | `DELETE_ARTIFACT` | Borrado lógico. |
| `GET /api/v1/artifacts/{artifact_id}/versions/` | `LIST_ARTIFACT_VERSIONS` | Historial de versiones. |
| `POST /api/v1/artifacts/{artifact_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Pulgar arriba/abajo (solo respuestas IA). |
| `DELETE /api/v1/artifacts/{artifact_id}/feedback/` | `SET_MESSAGE_FEEDBACK` | Quita feedback. |
| `POST /api/v1/artifacts/{artifact_id}/bookmark/` | `BOOKMARK_MESSAGE` | Marca artifact. |
| `DELETE /api/v1/artifacts/{artifact_id}/bookmark/` | `BOOKMARK_MESSAGE` | Quita marcador. |
| `POST /api/v1/artifacts/{artifact_id}/pin/` | `PIN_MESSAGE` | Fija en el chat. |
| `DELETE /api/v1/artifacts/{artifact_id}/pin/` | `PIN_MESSAGE` | Desfija. |
| `GET /api/v1/artifacts/{artifact_id}/thread/` | `LIST_THREAD_REPLIES` | Lista replies del hilo. |
| `POST /api/v1/artifacts/{artifact_id}/thread/` | `ADD_THREAD_REPLY` | Añade reply. |
| `GET /api/v1/artifacts/pinned/?chat_id=` | — | Lista fijados del chat (query `chat_id` obligatorio). |
| `GET /api/v1/artifacts/bookmarked/?chat_id=` | `LIST_BOOKMARKS` | Lista marcados del usuario en el chat. |
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

Por prefijo, en general:

| Rutas típicas | Permisos | Notas |
|---------------|----------|-------|
| `GET /` | `LIST_*` | Lista del usuario; filtro `chat_id` opcional. |
| `GET /manage/` | `MANAGE_*` | Lista admin. |
| `POST /generate/` | `LLM_*_GENERATE` | Generación IA; `chat_id` requerido en body (salvo donde el serializer lo indique). |
| `GET|PATCH|DELETE /{id}/` | `GET_*`, `UPDATE_*`, `DELETE_*` | CRUD del cuerpo tipado. |
| `GET /{id}/export/pdf|markdown/` | `EXPORT_*` | Descarga. |
| `GET /manage/{id}/export/...` | `MANAGE_EXPORT_*` | Export admin. |

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
