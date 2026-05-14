# Authentication & Authorization

## Overview

Every endpoint (except `/health` and `/ready`) requires authentication. The service supports two authentication modes:

1. **Service-to-service** — using a shared API key + user context headers
2. **Bearer token** — delegated to an external authentication provider

---

## Mode 1: Service-to-Service (API Key)

Used when another internal service calls `aura-llm-service` directly.

### Required Headers

| Header | Description |
|---|---|
| `X-Service-Api-Key` | Must match `SERVICE_API_KEY` env var (constant-time comparison) |
| `X-User-Id` | Numeric user ID (`int`) |
| `X-User-Email` | User email address |

### Optional Headers

| Header | Description |
|---|---|
| `X-User-Roles` | Comma-separated list of role strings |
| `X-User-Permissions` | Comma-separated list of permission strings |

### Example

```http
POST /api/v1/document-classify
X-Service-Api-Key: my-secret-key
X-User-Id: 42
X-User-Email: user@example.com
X-User-Permissions: LLM_DOCUMENT_CLASSIFY,LLM_DOCUMENT_QUESTION
Content-Type: application/json

{ ... }
```

---

## Mode 2: Bearer Token

Used when the request originates from a user-facing client via the API gateway.

```http
Authorization: Bearer <jwt-token>
```

The middleware forwards the token to the URL configured in `AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`. If the provider returns a valid user, the request proceeds. Errors map to:

| Provider Response | HTTP Status |
|---|---|
| Invalid / expired token | 401 |
| Access denied | 403 |
| User not found | 404 |
| Provider unreachable | 503 |

---

## Authenticated User Object

After successful authentication, a `AuthenticatedUser` model is available via `Depends(get_authenticated_user)` in every controller:

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

Each endpoint requires a specific permission. The caller must include this permission in `X-User-Permissions` (API-key mode) or have it granted by the auth provider (Bearer mode).

| Endpoint | Required Permission |
|---|---|
| `POST /document-question` | `LLM_DOCUMENT_QUESTION` |
| `POST /document-question/stream` | `LLM_DOCUMENT_QUESTION_STREAM` |
| `POST /document-summary` | `LLM_DOCUMENT_SUMMARY` |
| `POST /document-action` | `LLM_DOCUMENT_ACTION` |
| `POST /document-classify` | `LLM_DOCUMENT_CLASSIFY` |
| `POST /fragment-enrich` | `LLM_FRAGMENT_ENRICH` |
| `POST /graph-extraction` | `LLM_GRAPH_EXTRACTION` |
| `POST /graph-query-translation` | `LLM_GRAPH_QUERY_TRANSLATION` |
| `POST /agent` | `LLM_AGENT` |
| `POST /rag-agent` | `LLM_RAG_AGENT` |

Missing or wrong permission → `403 Forbidden`.

---

## Error Responses

All auth errors follow the standard error envelope:

```json
{
  "error": "UnauthorizedException",
  "message": "Missing or invalid authentication credentials"
}
```

| Scenario | Status | `error` field |
|---|---|---|
| No auth headers / no Bearer | 401 | `AuthenticationProviderInvalidTokenException` |
| Wrong API key | 403 | `AuthenticationProviderUnauthorizedException` |
| Missing `X-User-Id` | 400 | validation error |
| Non-integer `X-User-Id` | 400 | validation error |
| Missing `X-User-Email` | 400 | validation error |
| Insufficient permissions | 403 | `UnauthorizedException` |

---

## Public Endpoints (No Auth Required)

```
GET /api/v1/health
GET /api/v1/ready
GET /api/docs
GET /api/redoc
GET /api/openapi.json
GET /metrics
```
