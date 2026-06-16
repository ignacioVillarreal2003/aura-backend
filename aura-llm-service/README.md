# AURA LLM Service

Microservicio de IA de AURA. Expone una API REST (FastAPI) que orquesta un LLM
local servido por **Ollama** mediante **LangChain / LangGraph** para tareas de
interacción con el usuario (chat, RAG, resúmenes, quizzes, etc.) y de
procesamiento de documentos (clasificación, enriquecimiento, extracción y
traducción de consultas a grafo).

## Stack

- **Python 3.13+**, **FastAPI** + **Uvicorn**
- **LangChain / LangGraph** sobre **Ollama** (modelo por defecto `gemma3:1b`)
- **Redis** para rate limiting (ventana deslizante)
- Observabilidad opcional: métricas Prometheus, tracing OpenInference/Phoenix
- Guardrails opcionales (NeMo Guardrails), desactivados por defecto

## Arranque rápido

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements/requirements.txt
pip install -r requirements/requirements-dev.txt   # tests / herramientas

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Requiere Ollama accesible y Redis en ejecución. Pasos detallados, Docker y GPU:
ver [`docs/getting-started.md`](docs/getting-started.md).

Documentación interactiva una vez levantado:

- Swagger UI → `http://localhost:8001/api/docs`
- ReDoc → `http://localhost:8001/api/redoc`
- OpenAPI JSON → `http://localhost:8001/api/openapi.json`

## Configuración

Toda la configuración se lee por entorno vía `pydantic-settings`
(`app/configuration/environment_variables.py` y los `*_settings.py` de cada
módulo de infraestructura). Las variables de entorno tienen precedencia sobre
`.env`. La tabla completa de variables está en
[`docs/getting-started.md`](docs/getting-started.md#environment-variables).

> Las settings se construyen de forma perezosa y cacheada mediante
> `get_settings()` (no al importar el módulo), de modo que los tests pueden
> sobrescribir el entorno y limpiar la caché con `get_settings.cache_clear()`.

## Endpoints

Todos los endpoints cuelgan del prefijo `/api/v1`.

| Área | Prefijo | Tipo |
|---|---|---|
| Health / readiness | `/health`, `/ready` | operación (sin auth) |
| Chat general | `/general-chat` | interacción |
| Agente RAG | `/rag-agent` | interacción |
| Pregunta sobre documento | `/document-question` | interacción |
| Resumen de documento | `/document-summary` | interacción |
| Acción sobre documento | `/document-action` | interacción |
| Reporte / checklist / timeline / quiz | `/report-generate`, `/checklist-generate`, `/timeline-generate`, `/quiz-generate` | interacción |
| Lecciones aprendidas / brief de decisión | `/lessons-learned-generate`, `/decision-brief-generate` | interacción |
| Clasificación de documento | `/document-classify` | procesamiento |
| Enriquecimiento de fragmentos | `/fragment-enrich` | procesamiento |
| Extracción a grafo | `/graph-extraction` | procesamiento |
| Traducción de consulta a grafo | `/graph-query-translation` | procesamiento |

Detalle de cuerpos de petición/respuesta: [`docs/api-reference.md`](docs/api-reference.md).
Autenticación (Bearer): [`docs/authentication.md`](docs/authentication.md).
Rate limiting: [`docs/rate-limiting.md`](docs/rate-limiting.md).

## Health checks

```
GET /api/v1/health   →  200 siempre (liveness, sin auth)
GET /api/v1/ready    →  200 si dependencias OK, 503 si alguna falla (readiness)
```

`/ready` verifica cliente HTTP, Ollama y Redis. Cada verificación de I/O tiene un
timeout por dependencia para que una dependencia colgada no bloquee el probe ni
saque el pod de rotación. Usar `/ready` en `HEALTHCHECK` de Docker y
`readinessProbe` de Kubernetes.

## Tests

```bash
pytest -q
```

Los tests usan `starlette.TestClient` con un lifespan no-op; Ollama y los
servicios externos se reemplazan por `AsyncMock` (ver `test/conftest.py`). El
entorno de test debe proveer las variables requeridas (p. ej. `CORS_ORIGINS` y
las URLs de los proveedores).

## Runbook operativo

- **El servicio no levanta por config** → falta una variable requerida (p. ej.
  `CORS_ORIGINS`, URLs del proveedor de auth/documentos). El error de validación
  de `pydantic-settings` indica el campo faltante.
- **`/ready` devuelve 503** → revisar el campo `checks` de la respuesta para ver
  qué dependencia falla (`http_client`, `ollama`, `redis`): `not_configured`
  (no inicializada en el arranque), `error` (falló o superó el timeout).
- **429 Too Many Requests** → rate limit superado; el header `Retry-After`
  indica los segundos a esperar. Ajustar `RATE_LIMIT_*`. Si Redis no está
  disponible el rate limiting es *fail-open* (se permite la petición).
- **Latencia alta / timeouts del LLM** → revisar disponibilidad de Ollama y
  `OLLAMA_LLM_FACADE_TIMEOUT`; el `http_client` usa circuit breaker por host.
- **Tracing / métricas** → métricas Prometheus en `/metrics`; tracing
  desactivado salvo `TRACING_ENABLED=true`.
