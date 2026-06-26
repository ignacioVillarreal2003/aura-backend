# Getting Started

## Prerequisites

- Python 3.13+
- [Ollama](https://ollama.ai) running locally (or reachable via network)
- Redis (for the token cache and rate limiting)
- A model pulled in Ollama, matching `OLLAMA_LLM_FACADE_MODEL_NAME` (required, no
  built-in default). The local `.env` uses `gemma4:e2b`; the CPU Docker env uses
  `gemma3:1b`.

```bash
ollama pull gemma4:e2b   # or whatever you set in OLLAMA_LLM_FACADE_MODEL_NAME
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

Edit the env file (`.env` at the repo root). At minimum it must define the
required variables: `CORS_ORIGINS`, `OLLAMA_LLM_FACADE_MODEL_NAME`,
`OLLAMA_LLM_FACADE_BASE_URL`, the document/graph context provider URLs,
`REDIS_CLIENT_URL` and `AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`.

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

Only the deployment-specific values live in `.env`; everything else uses the
defaults baked into the settings classes (tuned for an RTX 3050 8 GB GPU). The
tables below list the most relevant variables — each settings class ignores
unknown keys, so extra tunables can be added with the matching prefix.

### Core

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `aura llm service` | Application name (shown in OpenAPI) |
| `APP_VERSION` | `1.0.0` | Application version |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Bind port (the local `.env` uses `8001`) |
| `APP_RELOAD` | `false` | Enable Uvicorn hot-reload |
| `LOG_LEVEL` | `INFO` | One of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `CORS_ORIGINS` | — (**required**) | JSON list of allowed CORS origins; must be non-empty |
| `ENVIRONMENT` | `development` | `production`/`prod` ⇒ production mode (affects CORS-credentials handling and startup logging) |
| `MAX_REQUEST_BODY_BYTES` | `10485760` (10 MiB) | Requests with a larger body are rejected with `413` |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window size for rate limiting |
| `RATE_LIMIT_DEFAULT_PER_WINDOW` | `60` | Requests allowed per window on default-tier endpoints |
| `RATE_LIMIT_STRICT_PER_WINDOW` | `20` | Requests allowed per window on strict-tier (streaming/heavy) endpoints |

### Authentication Provider

| Variable | Default | Description |
|---|---|---|
| `AUTHENTICATION_PROVIDER_AUTHENTICATION_URL` | — (**required**) | URL called to validate Bearer tokens |
| `AUTHENTICATION_PROVIDER_REQUEST_TIMEOUT_SECONDS` | `15` | HTTP timeout in seconds |
| `AUTHENTICATION_PROVIDER_TOKEN_CACHE_TTL_SECONDS` | `60` | TTL for cached validated tokens (Redis) |

### Ollama LLM (`OLLAMA_LLM_FACADE_*`)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_LLM_FACADE_BASE_URL` | — (**required**) | Ollama server URL |
| `OLLAMA_LLM_FACADE_MODEL_NAME` | — (**required**) | Model to load |
| `OLLAMA_LLM_FACADE_NUM_CTX` | `24576` | Context window (tokens); lower it if the model spills to CPU |
| `OLLAMA_LLM_FACADE_NUM_PREDICT` | `6144` | Max output tokens |
| `OLLAMA_LLM_FACADE_TEMPERATURE` | `0.2` | Sampling temperature |
| `OLLAMA_LLM_FACADE_REPEAT_PENALTY` | `1.05` | Repetition penalty |
| `OLLAMA_LLM_FACADE_KEEP_ALIVE` | `30m` | How long Ollama keeps the model loaded (`-1` = forever) |
| `OLLAMA_LLM_FACADE_REQUEST_TIMEOUT` | `300` | LLM call timeout in seconds |

### LLM Concurrency

| Variable | Default | Description |
|---|---|---|
| `LLM_MAX_CONCURRENCY` | `4` | Max simultaneous LLM calls per worker |

### Document / Graph Context Providers

| Variable | Default | Description |
|---|---|---|
| `DOCUMENT_CONTEXT_PROVIDER_QUESTION_CONTEXT_FRAGMENTS_URL` | — (**required**) | Fragment retrieval endpoint for question answering |
| `DOCUMENT_CONTEXT_PROVIDER_DOCUMENT_CONTEXT_FRAGMENTS_URL` | — (**required**) | Fragment retrieval endpoint by document IDs |
| `DOCUMENT_CONTEXT_PROVIDER_TIMEOUT_SECONDS` | `120` | HTTP timeout in seconds |
| `GRAPH_CONTEXT_PROVIDER_URL` | — | Knowledge-graph context endpoint (graph enrichment is skipped if unset) |
| `GRAPH_CONTEXT_PROVIDER_TIMEOUT_SECONDS` | `15` | HTTP timeout in seconds |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_CLIENT_URL` | — (**required**) | Redis connection URL, e.g. `redis://127.0.0.1:6379/0`. Used for the token cache and rate limiting; if unreachable at startup the service continues without them |

### Tracing & Guardrails (optional)

| Variable | Default | Description |
|---|---|---|
| `TRACING_ENABLED` | `false` | Send OpenInference spans to Phoenix |
| `TRACING_ENDPOINT` | `http://localhost:6006/v1/traces` | OTLP traces endpoint |
| `NEMO_GUARDRAILS_ENABLED` | `true` | Enable the NeMo input guardrail |
| `NEMO_GUARDRAILS_CHECK_OUTPUT` | `false` | Also screen LLM output |

### RAG agent tunables (`RAG_AGENT_*`, optional)

| Variable | Default | Description |
|---|---|---|
| `RAG_AGENT_USE_CONTEXT_GRADER` | `true` | Enable Corrective-RAG context grading + query refinement |
| `RAG_AGENT_MAX_RETRIEVAL_ATTEMPTS` | `1` | Max corrective re-retrieval loops |
| `RAG_AGENT_USE_GRAPH_STRUCTURED_QUERY` | `true` | Run the structured graph query for relational intents |

---

## Health Check

```
GET /api/v1/health   →  200 OK  (always, no auth)
GET /api/v1/ready    →  200 OK if HTTP client + Ollama + Redis are healthy, else 503
```

`/ready` checks each dependency with a short per-dependency timeout, so a hung
dependency yields a fast `503` instead of stalling the probe. The response body
includes a `checks` object with the per-dependency status. Use `/ready` in
Docker `HEALTHCHECK` and Kubernetes `readinessProbe`.

---

## Running Tests

```bash
pytest -q
```

Tests use `starlette.TestClient` with a noop lifespan (no Ollama or external services required). All services are replaced with `AsyncMock` fixtures defined in `test/conftest.py`.

### Coverage

CI runs the suite with branch coverage and fails below a **75 %** combined floor
(critical paths — error handlers, rate limiting, the `http_client` circuit
breaker and DI startup/rollback — have dedicated unit tests). To reproduce the
gate locally:

```bash
pytest -q --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=75
```

The test environment must provide the required settings (e.g. `CORS_ORIGINS`
and the provider URLs); CI sets these in the workflow.
