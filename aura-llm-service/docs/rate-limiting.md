# Rate Limiting & Idempotency

## Rate Limiting

Rate limiting is enforced per-user (authenticated) or per-IP (unauthenticated) using a **sliding window** algorithm backed by Redis sorted sets.

### Limits

| Tier | Requests / window (default) | Applied to |
|---|---|---|
| Default | 60 | `/document-question`, `/document-classify`, `/fragment-enrich`, `/graph-extraction`, `/graph-query-translation` |
| Strict | 20 | `/document-question/stream`, `/document-summary`, `/document-action`, `/agent`, `/rag-agent` |

Window size and per-tier limits are configurable via `RATE_LIMIT_WINDOW_SECONDS`, `RATE_LIMIT_DEFAULT_PER_WINDOW` and `RATE_LIMIT_STRICT_PER_WINDOW` (see [getting-started](getting-started.md)).

### Redis key format

```
rl:{identity}:{request_path}
```

Where `identity` is the authenticated user's ID or the client's IP address.

### Exceeded limit response

```
HTTP/1.1 429 Too Many Requests
Retry-After: 42
```

```json
{
  "error": "HttpError",
  "message": "Rate limit exceeded. Please retry later.",
  "request_id": "..."
}
```

### Disabling rate limiting in tests

The `test/conftest.py` noop lifespan skips Redis initialisation. Rate-limit dependencies are resolved at request time and will fail gracefully (returning 503) if Redis is unavailable — the tests mock the service layer before the rate limiter is reached, so no Redis is needed.

---

## Idempotency Keys

Endpoints that trigger LLM calls support optional idempotency via the `Idempotency-Key` header.

```http
POST /api/v1/document-summary
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

### Behaviour

- If no header is provided the request is processed normally.
- If a key is provided and a cached response for that key exists, the cached response is returned without calling the LLM.
- Keys are scoped per user — two different users can use the same key without collision.

### When to use

Send an idempotency key whenever you might retry a request on network failure. Use a stable UUID generated client-side per logical operation:

```python
import uuid
idempotency_key = str(uuid.uuid4())  # generate once per operation, reuse on retries
```

### Covered endpoints

| Endpoint | Idempotency supported |
|---|---|
| `POST /document-question` | yes |
| `POST /document-question/stream` | no |
| `POST /document-summary` | yes |
| `POST /document-action` | yes |
| `POST /document-classify` | yes |
| `POST /fragment-enrich` | yes |
| `POST /graph-extraction` | yes |
| `POST /graph-query-translation` | yes |
| `POST /agent` | yes |
| `POST /rag-agent` | yes |
