# Authentication & Authorization

## Overview

Every endpoint requires a Bearer token except the public paths listed at the
bottom. Authentication is **JWT/Bearer only** — the token is validated by an
external authentication provider; there is no service-to-service API-key mode.

---

## Bearer Token

```http
Authorization: Bearer <jwt-token>
```

An ASGI middleware extracts the token and forwards it to the URL configured in
`AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`. If the provider returns a valid
user, the request proceeds and the validated user is attached to the request
state. Validated tokens are cached in Redis for
`AUTHENTICATION_PROVIDER_TOKEN_CACHE_TTL_SECONDS` (default 60 s), so a revoked
token may remain accepted until the cache entry expires.

Error mapping:

| Situation | HTTP Status |
|---|---|
| Missing token / not in `Bearer <token>` format | 401 |
| Bearer token longer than the configured maximum | 401 |
| Invalid / expired token | 401 |
| Access denied by the provider | 403 |
| User not found | 404 |
| Provider unreachable / timeout / circuit open | 503 |
| Auth provider not configured on the app | 503 |

---

## Authenticated User Object

After successful authentication, an `AuthenticatedUser` model is available via
`Depends(get_authenticated_user)` in every controller:

```python
class AuthenticatedUser:
    id: int
    email: str
    roles: list[str]       # e.g. ["ADMIN", "USER"]
    permissions: list[str] # e.g. ["LLM_DOCUMENT_QUESTION", "LLM_AGENT"]
```

Helper methods:
- `has_role(role)` — exact match
- `has_any_role(roles_set)` — union check
- `has_permission(permission)` — exact match
- `has_any_permission(perms_set)` — union check
- `has_all_permissions(perms_set)` — intersection check

---

## Permissions

Each endpoint requires a specific permission, granted by the auth provider in
the validated user. A `/stream` variant requires the same permission as its base
endpoint.

| Endpoint | Required Permission |
|---|---|
| `POST /document-question` (`/stream`) | `LLM_DOCUMENT_QUESTION` |
| `POST /document-summary` (`/stream`) | `LLM_DOCUMENT_SUMMARY` |
| `POST /document-action` (`/stream`) | `LLM_DOCUMENT_ACTION` |
| `POST /document-classify` | `LLM_DOCUMENT_CLASSIFY` |
| `POST /fragment-contextualize` | `LLM_FRAGMENT_CONTEXTUALIZE` |
| `POST /graph-extraction` | `LLM_GRAPH_EXTRACTION` |
| `POST /graph-query-translation` | `LLM_GRAPH_QUERY_TRANSLATION` |
| `POST /general-chat` (`/stream`) | `LLM_GENERAL_CHAT` |
| `POST /rag-agent` (`/stream`) | `LLM_AGENT` |
| `POST /report-generate` (`/stream`) | `LLM_REPORT_GENERATE` |
| `POST /checklist-generate` (`/stream`) | `LLM_CHECKLIST_GENERATE` |
| `POST /timeline-generate` (`/stream`) | `LLM_TIMELINE_GENERATE` |
| `POST /quiz-generate` (`/stream`) | `LLM_QUIZ_GENERATE` |
| `POST /lessons-learned-generate` (`/stream`) | `LLM_LESSONS_LEARNED_GENERATE` |
| `POST /decision-brief-generate` (`/stream`) | `LLM_DECISION_BRIEF_GENERATE` |

Missing or wrong permission → `403 Forbidden` (`UnauthorizedException`).

---

## Error Responses

All auth errors follow the standard error envelope:

```json
{
  "error": "AuthenticationProviderInvalidTokenException",
  "message": "Invalid or expired token",
  "request_id": "optional-uuid"
}
```

---

## Public Endpoints (No Auth Required)

```
GET /
GET /api/health
GET /api/v1/health
GET /api/v1/ready
GET /api/docs
GET /api/redoc
GET /api/openapi.json
GET /metrics
```
