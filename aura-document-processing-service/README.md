# aura-document-processing-service

Microservicio de procesamiento de documentos de la plataforma **AURA**. Expone una API
HTTP (FastAPI) y consumidores de mensajería para **ingesta**, **recuperación** y, de forma
opcional, **grafo de conocimiento** sobre documentos.

## Qué hace

- **Ingesta**: subida de archivo → lectura (PDF/DOCX/…) → limpieza → *splitting* semántico →
  *embeddings* → persistencia (PostgreSQL + `pgvector`) y almacenamiento del binario (MinIO).
  La ingesta pesada se procesa de forma asíncrona vía RabbitMQ.
- **Recuperación**: búsqueda híbrida (vectorial + BM25 full-text) con *reranking* por
  *cross-encoder*; búsqueda y descarga de documentos.
- **Grafo de conocimiento** (opcional, `KNOWLEDGE_GRAPH_ENABLED=true`): extracción de
  entidades/relaciones y consultas sobre Neo4j.

## Arquitectura

Capas con interfaces explícitas e inyección de dependencias en el arranque (`app.state`):

```
app/
  api/            # Controllers (routers FastAPI), schemas, middlewares, handlers de error
  application/    # Servicios (lógica de negocio), processors (readers/embedders/...), authorization
  domain/         # DTOs, constantes, tipos, modelos de dominio
  infrastructure/ # Persistencia (DB/Neo4j/MinIO/Redis), mensajería (RabbitMQ), clientes HTTP
  configuration/  # Arranque/teardown de dependencias, logging, CORS, settings de app
```

Stack: **FastAPI**, **SQLAlchemy 2 async** + `asyncpg` + `pgvector` (+ ParadeDB para BM25),
**Redis**, **RabbitMQ** (`aio-pika`), **MinIO**, **Neo4j** (opcional), **LangChain** /
`sentence-transformers` / `docling`. Observabilidad: logging JSON estructurado con
`request_id` y métricas Prometheus.

## Requisitos

- Python **3.13**
- Servicios externos: PostgreSQL (con `pgvector`/ParadeDB), Redis, RabbitMQ, MinIO y —si se
  habilita el grafo— Neo4j. Tesseract/Poppler para OCR (ya incluidos en la imagen Docker).

## Puesta en marcha (local)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements/requirements.txt        # CPU; usar requirements.gpu.txt para GPU
cp .env .env.local   # ajustar credenciales/URLs según tu entorno
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> La configuración se carga desde variables de entorno (fichero `.env`). **No** se deben
> commitear secretos reales: usa un gestor de secretos en despliegues productivos.

## Docker

```bash
docker build -t aura-document-processing-service .            # CPU
docker build -f DockerfileGPU -t aura-document-processing-service:gpu .   # GPU (CUDA)
```

La imagen baja los modelos en *build* (sin red en runtime), corre como usuario no root y
define `HEALTHCHECK` contra `/api/v1/health`.

## Endpoints

- API versionada: `/api/v1/...`
- Documentación: `/api/docs` (Swagger), `/api/redoc`, `/api/openapi.json`
- **Liveness**: `GET /api/v1/health` · **Readiness**: `GET /api/v1/ready` (verifica
  Redis/DB/RabbitMQ/MinIO; 200 ok / 503 degradado)
- Métricas Prometheus: `/metrics`

Todas las rutas de negocio requieren `Authorization: Bearer <token>` (validado contra el
servicio de autenticación) y permisos por endpoint.

## Tests y calidad

```bash
pytest                       # suite de tests (asyncio_mode=auto, ver pyproject.toml)
ruff check app               # lint (reglas de alto valor; gate verde)
mypy                         # tipado (baseline incremental)
```

La configuración de `ruff`, `mypy` y `pytest` vive en `pyproject.toml`.

## Documentación adicional

Ver `docs/` (API, adapters de readers/embedders/splitters, modelos de embedding).
