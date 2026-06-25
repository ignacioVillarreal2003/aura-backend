# Documentación — Aura Document Processing Service

Servicio FastAPI para **ingesta, procesamiento, indexación y consulta** de documentos y sus
fragments (RAG): lectura → limpieza → chunking → embedding → persistencia (pgvector + BM25),
con enriquecimiento por LLM, **contextual retrieval** y un módulo opcional de **knowledge graph**.

La **fuente de verdad ejecutable** de los contratos HTTP es OpenAPI (`/api/openapi.json`,
Swagger en `/api/docs`). Estos docs describen la arquitectura y la configuración.

## Pipeline de ingesta

```
upload → validación (magic numbers, tamaño, extensión) → object storage (MinIO)
       → persist documento (status=uploaded) → publish a cola (RabbitMQ + outbox)
consumer → reader → text cleaner → text splitter → embedder → persist fragments (status=processed)
       → (opcional) enrich: clasificación + contextualización   → (opcional) graph extraction
```

## Índice

### Adapters (componentes intercambiables por configuración)
- [Readers](adapters/readers.md) — extracción de texto (Docling-first + fallback secuencial, OCR).
- [Text Cleaners](adapters/text_cleaners.md) — normalización de texto.
- [Text Splitters](adapters/text_splitters.md) — chunking de dos niveles (docling_hybrid + semántico).
- [Embedders](adapters/embedders.md) — vectorización (bge-m3, HuggingFace/Ollama).
- [Rerankers](adapters/rerankers.md) — re-ranking cross-encoder (bge-reranker-v2-m3).

### Retrieval
- [Contextual Retrieval](retrieval/contextual_retrieval.md) — representación dual + RRF multi-lane.

### Modelos
- [Embedding (HuggingFace)](embedding/huggingface_embedding_models.md)
- [Embedding (Ollama)](embedding/ollama_embedding_models.md)
- [Modelos del splitter semántico](splitting/huggingface_text_splitter_models.md)

### API HTTP
- [Overview](api/overview.md) · [Autenticación](api/authentication.md) ·
  [Endpoints](api/endpoints.md) · [Flujos de documentos](api/documents.md)

## Defaults de producción (resumen)

| Componente | Default |
| --- | --- |
| Embedder | `BAAI/bge-m3` (1024-dim, GPU, dtype `auto`, seq 8192) |
| Reranker | `BAAI/bge-reranker-v2-m3` (max_length 1024) |
| Text splitter | `docling_hybrid` → fallback `huggingface` (bge-m3) |
| Reader | Docling-first + fallback secuencial |
| Contextual retrieval | activo (representación dual + RRF) |

> Configuración por entorno: `.env` (local), `env/.env.docker` (CPU/Ollama),
> `env/.env.docker.gpu` (GPU/HuggingFace). Los invariantes de producción
> (`production_invariants.py`) impiden arrancar con configuración insegura (secretos débiles,
> CORS `*`, TLS faltante, etc.).
