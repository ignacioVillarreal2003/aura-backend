# Aura Notification Service

Centralised notification API for the Aura platform. Other microservices
push semantic events here; this service decides which channels to use
(in-app, email), persists the in-app row, queues the email, and pushes
real-time updates to the frontend over Server-Sent Events.

Extended **Spanish** API guide (architecture, auth modes, endpoints, producers, SSE, operations): **[docs/README.md](docs/README.md)**.

## Capabilities

- REST API under `/api/v1/`.
- Per-user inbox: list / mark read / soft delete / unread count /
  mark-all-read.
- Per-user preferences: global in-app/email toggles and mute-until.
- Catalogue of supported event types (publicly readable so the frontend
  can render the preferences screen without hard-coding metadata).
- Internal `POST /api/v1/internal/events/` used by other services.
- Back-compat `POST /api/internal/notification/admin-create/` kept so
  `aura-auth-service` keeps working without changes.
- Email rendering through Django templates per event type
  (`apps/notification/templates/notifications/<template_id>/`).
- Email dispatch via Celery + RabbitMQ with exponential-backoff retries.
- Realtime via Redis pub/sub + Server-Sent Events
  (`GET /api/v1/notifications/stream/`).
- Auth aligned with the rest of the stack
  (`AuthenticationMiddleware` validating bearer JWTs against the central
  authentication service + `X-Service-Api-Key` for service-to-service).

## Architecture

```
producer (chat / auth / docs)
        │  POST /api/v1/internal/events
        ▼
  aura-notification-service (gunicorn)
        │ resolves preferences + templates
        ├──► Postgres aura_db (notification, email_dispatch, notification_preference)
        ├──► Redis pub/sub (notif:user:{id})  ──► SSE stream  ──► Frontend
        └──► RabbitMQ ──► Celery worker ──► SMTP
```

## Endpoints

### End-user (Bearer JWT)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/api/v1/notifications/` | Paginated inbox |
| GET    | `/api/v1/notifications/unread-count/` | `{count}` |
| GET    | `/api/v1/notifications/{id}/` | Detail |
| PATCH  | `/api/v1/notifications/{id}/` | `{status: read | unread}` |
| DELETE | `/api/v1/notifications/{id}/` | Soft delete |
| POST   | `/api/v1/notifications/mark-all-read/` | `{until_id?: int}` |
| GET    | `/api/v1/notifications/stream/` | SSE stream |
| GET    | `/api/v1/me/notification-preferences/` | Global preferences |
| PUT    | `/api/v1/me/notification-preferences/` | Update global prefs |

### Public (no auth)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET    | `/api/v1/event-types/` | Catalogue used by the frontend |
| GET    | `/api/v1/health` | Liveness + dependency probe |
| GET    | `/api/schema/` `/api/docs/` `/api/redoc/` | OpenAPI |

### Internal (`X-Internal-Token`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST   | `/api/v1/internal/events/` | Producer entry point (recommended) |
| POST   | `/api/v1/internal/notifications/admin-create/` | Admin broadcast |
| POST   | `/api/internal/notification/admin-create/` | Legacy alias for aura-auth-service |

## Event registry

Defined in [`apps/notification/events/registry.py`](apps/notification/events/registry.py).
Adding a new event = constant in `EventType`, an entry in `_EVENTS`,
and template files under `apps/notification/templates/notifications/<template_id>/`.

| `event_type`                       | Default channels | Silenceable | Template id |
| ---------------------------------- | ---------------- | ----------- | ----------- |
| `chat.member.invited`              | inapp            | yes         | `chat_member_invited` |
| `chat.member.removed`              | inapp            | yes         | `chat_member_removed` |
| `chat.locked`                      | inapp            | yes         | `chat_locked` |
| `auth.password.changed`            | inapp + email    | **no**      | `auth_password_changed` |
| `auth.new_login`                   | email            | yes         | `auth_new_login` |
| `document.processing.done`         | inapp            | yes         | `document_processing_done` |
| `document.processing.failed`       | inapp + email    | yes         | `document_processing_failed` |
| `admin.broadcast`                  | inapp            | yes         | `admin_broadcast` |
| `system.announcement`              | inapp            | **no**      | `system_announcement` |

## Producer example

Any service inside the cluster can do:

```http
POST /api/v1/internal/events/ HTTP/1.1
Host: aura-notification-service:8000
Content-Type: application/json
X-Internal-Token: dev-notification-internal-token

{
  "event_type": "chat.member.invited",
  "recipient_ids": [12, 13],
  "actor_id": 7,
  "actor_name": "ten.lopez",
  "context": {
    "chat_id": 42,
    "chat_name": "Operación X",
    "recipient_email": "lopez@faa.mil.ar"
  },
  "link_url": "https://app.local/chats/42"
}
```

Pass `recipient_email` inside `context` whenever you already have it
(saves a round-trip to the auth service when the email channel is
enabled). Otherwise the worker calls `${AUTHENTICATION_SERVICE_URL}/auth/users/{id}`
to look it up.

## Schema

The Django models are `managed = False`; the schema lives in
[`docker/database/aura-db/notification.sql`](../docker/database/aura-db/notification.sql).
Apply it on the existing database as part of the aura-db init scripts.

## Local dev

```bash
cd aura-notification-service

# 1. install deps
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. apply the schema (from repo root)
psql -h 127.0.0.1 -U aura_root -d aura_db -f docker/database/aura-db/notification.sql

# 3. run the API
python manage.py runserver 0.0.0.0:8004

# 4. (in another shell) run the Celery worker
celery -A aura_notification_service worker -l info -Q notifications

# On Windows the default prefork pool often crashes (billiard spawn); use solo or threads:
# celery -A aura_notification_service worker -l info -Q notifications --pool=solo
```

## Testing the SSE stream

```bash
curl -N -H "Authorization: Bearer user_token_123" \
     http://localhost:8004/api/v1/notifications/stream/
```

In another terminal, fire an event:

```bash
curl -X POST http://localhost:8004/api/v1/internal/events/ \
     -H "Content-Type: application/json" \
     -H "X-Internal-Token: dev-notification-internal-token" \
     -d '{
       "event_type": "system.announcement",
       "recipient_ids": [12],
       "context": {"message": "Mantenimiento mañana 03:00 UTC"}
     }'
```

The first terminal will receive a `notification.created` event in real time.

## Configuration

All configuration is via environment variables. See `.env` and
`.env.docker` for the full list. The most relevant:

| Variable | Purpose |
| -------- | ------- |
| `AUTHENTICATION_SERVICE_URL` | Base URL of the central auth (e.g. mock-auth on `:8080`) |
| `SERVICE_API_KEY` | Shared secret for `X-Service-Api-Key` calls |
| `NOTIFICATION_INTERNAL_API_TOKEN` | Token expected on `X-Internal-Token` |
| `REDIS_URL` | Cache + SSE pub/sub (`redis://memory_db:6379/2` in docker) |
| `CELERY_BROKER_URL` | RabbitMQ AMQP URL (`amqp://...@queue:5672//`) |
| `CELERY_RESULT_BACKEND` | Redis-backed (`redis://memory_db:6379/3`) |
| `EMAIL_BACKEND` / `EMAIL_HOST` / ... | SMTP config (defaults to console) |
| `NOTIFICATION_DEFAULT_LINK_BASE_URL` | Used by the registry link builders |
| `NOTIFICATION_SSE_HEARTBEAT_SECONDS` | Default 15 |
| `NOTIFICATION_SSE_MAX_DURATION_SECONDS` | Default 1800 |
| `NOTIFICATION_HARD_DELETE_DAYS` | Retention before `purge_notifications` cleans soft-deleted rows |

## Operational tasks

- `python manage.py purge_notifications [--days N] [--dry-run]` — Hard
  deletes soft-deleted rows older than the configured threshold.

## Why no migrations?

The notification tables span service boundaries (read by
`aura-auth-service` admin) and the project chose a single source of
truth in SQL. `MIGRATION_MODULES` disables Django migrations for the
local app and every model declares `managed = False`. The accompanying
[`docker/database/aura-db/notification.sql`](../docker/database/aura-db/notification.sql) is the operational source of truth.
