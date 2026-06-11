# Getting Started

## Prerequisites

- Python 3.13+
- [Ollama](https://ollama.ai) running locally (or reachable via network)
- Redis (for rate limiting)
- The model pulled in Ollama — default: `gemma3:1b`

```bash
ollama pull gemma3:1b
```

---

## Local Setup

```bash
cd aura-llm-service

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements/requirements.txt
pip install -r requirements/requirements-dev.txt   # for tests / dev tools
```

Copy and edit the env file:

```bash
cp .env.example .env   # or edit .env directly
```

Run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## Docker

```bash
docker compose up aura-llm-service
```

The service starts on port `8001`. Ollama is expected at `http://llm:11434` (see `docker-compose.yml`).

For GPU acceleration:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up aura-llm-service
```

---

## Environment Variables

All variables are read by `app/configuration/environment_variables.py` via `pydantic-settings`. Environment variables always take precedence over values in `.env`.

### Core

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `aura llm service` | Application name (shown in OpenAPI) |
| `APP_VERSION` | `1.0.0` | Application version |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Bind port (override to `8001` in practice) |
| `APP_RELOAD` | `false` | Enable Uvicorn hot-reload |
| `LOG_LEVEL` | `INFO` | One of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `CORS_ORIGINS` | `["*"]` | JSON list of allowed CORS origins |
| `ENVIRONMENT` | `development` | Arbitrary label; no functional effect |
| `SERVICE_API_KEY` | `service_api_key` | Secret shared with other services for internal auth (a startup warning is logged if left at this default) |
| `MAX_REQUEST_BODY_BYTES` | `10485760` (10 MiB) | Requests with a larger body are rejected with `413` |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window size for rate limiting |
| `RATE_LIMIT_DEFAULT_PER_WINDOW` | `60` | Requests allowed per window on default-tier endpoints |
| `RATE_LIMIT_STRICT_PER_WINDOW` | `20` | Requests allowed per window on strict-tier endpoints |

### Authentication Provider

| Variable | Default | Description |
|---|---|---|
| `AUTHENTICATION_PROVIDER_AUTHENTICATION_URL` | — | URL called to validate Bearer tokens |
| `AUTHENTICATION_PROVIDER_TIMEOUT` | `30` | HTTP timeout in seconds |

### Ollama LLM

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_LLM_FACADE_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_LLM_FACADE_MODEL_NAME` | `gemma3:1b` | Model to load |
| `OLLAMA_LLM_FACADE_TEMPERATURE` | `0.7` | Sampling temperature |
| `OLLAMA_LLM_FACADE_TIMEOUT` | `120` | LLM call timeout in seconds |

### Document Context Provider

| Variable | Default | Description |
|---|---|---|
| `DOCUMENT_CONTEXT_PROVIDER_QUESTION_CONTEXT_FRAGMENTS_URL` | — | Fragment retrieval endpoint for question answering |
| `DOCUMENT_CONTEXT_PROVIDER_DOCUMENT_CONTEXT_FRAGMENTS_URL` | — | Fragment retrieval endpoint for document context |

### Redis (Rate Limiting)

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |

---

## Health Check

```
GET /api/v1/health   →  200 OK  (always, no auth)
GET /api/v1/ready    →  200 OK if Ollama + HTTP client are available, else 503
```

Use `/ready` in Docker `HEALTHCHECK` and Kubernetes `readinessProbe`.

---

## Running Tests

```bash
pytest test/ -v
```

Tests use `starlette.TestClient` with a noop lifespan (no Ollama or external services required). All services are replaced with `AsyncMock` fixtures defined in `test/conftest.py`.
