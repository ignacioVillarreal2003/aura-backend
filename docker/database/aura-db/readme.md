# Aura DB (PostgreSQL)

El esquema inicial y los datos de seed están en **`init.sql`** (entrada de Docker `docker-entrypoint-initdb.d`).

Los valores antes modelados como `ENUM` de PostgreSQL están en columnas **`VARCHAR(64)`**; los conjuntos válidos los define la aplicación/API.

Incluye, entre otros:

- **chat**: columnas `tags`, `is_ephemeral`, `is_locked`
- **chat_membership**: `pinned_at`, `archived_at`, `last_read_at`, `role`, `muted_until`; unicidad `(member_id, chat_id)` solo cuando `deleted_at IS NULL`; índice `(chat_id, member_id, status)`
- **chat_message**: índice `(chat_id, created_at DESC)` para paginación por cursor
- **Tablas**: `pinned_message`, `message_bookmark`, `message_thread_reply`, `message_feedback`, `chat_share_link`, `chat_webhook`

Para bases ya existentes, migrá con deltas equivalentes a lo definido arriba (ALTER / CREATE INDEX / CREATE TABLE) en el orden correcto según FKs.
