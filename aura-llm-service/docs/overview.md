# aura-llm-service — Overview

## What It Does

`aura-llm-service` is an internal FastAPI microservice that wraps a locally-hosted Ollama LLM and exposes structured endpoints for language-model tasks: answering questions about documents, summarising, executing free-form instructions, classifying documents, enriching text fragments, extracting knowledge-graph entities, translating natural-language graph queries, and running agentic workflows.

All endpoints are **internal-only** — they require a validated Bearer token forwarded by the API gateway (see [authentication.md](authentication.md)).

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI Application                  │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Middleware layer                                   │ │
│  │  • Logging (request ID, latency)                   │ │
│  │  • Authentication (Bearer token)                   │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                               │
│  ┌───────────────────────▼─────────────────────────────┐ │
│  │  Controllers  (app/api/controllers/)                │ │
│  │  • Validate request body (Pydantic v2)              │ │
│  │  • Check permissions (Authorizer)                   │ │
│  │  • Apply rate limit                                 │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                               │
│  ┌───────────────────────▼─────────────────────────────┐ │
│  │  Services  (app/application/services/)              │ │
│  │  • Orchestrate LLM calls via LangChain / LangGraph  │ │
│  │  • Retrieve document context (external HTTP)        │ │
│  └──────────┬─────────────────────┬─────────────────────┘ │
│             │                     │                       │
│  ┌──────────▼──────────┐  ┌───────▼──────────────────┐   │
│  │ Ollama LLM Facade   │  │ Document Context Provider │   │
│  │ (local Ollama)      │  │ (aura-document-processing)│   │
│  └─────────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Layers

| Layer | Path | Responsibility |
|---|---|---|
| Controllers | `app/api/controllers/` | HTTP routing, request validation, permission checks |
| Services | `app/application/services/` | Business logic, LLM orchestration |
| Domain | `app/domain/` | DTOs, constants, field limits, auth models |
| Infrastructure | `app/infrastructure/` | Ollama client, external HTTP, auth provider |
| Configuration | `app/configuration/` | Env vars, CORS, middlewares, logging |

---

## Tech Stack

| Concern | Library |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Data validation | Pydantic v2 |
| LLM orchestration | LangChain Core + LangGraph |
| LLM backend | Ollama (local; model via `OLLAMA_LLM_FACADE_MODEL_NAME`) |
| HTTP client | httpx (async) |
| Rate limiting | Redis (sorted-set sliding window) |
| Metrics | Prometheus (`prometheus-fastapi-instrumentator`) |
| Structured logging | custom JSON formatter (stdlib `logging`) |
| Tracing | OpenInference → Phoenix (OTLP), optional |

---

## Endpoints at a Glance

Most user-interaction endpoints also expose a `POST …/stream` variant
(`text/event-stream`); the streaming variant is rate-limited at 20 / min and
requires the same permission as its base endpoint.

| Method | Path | Permission | Rate limit |
|---|---|---|---|
| GET | `/api/v1/health` | — | — |
| GET | `/api/v1/ready` | — | — |
| POST | `/api/v1/document-question` (`/stream`) | `LLM_DOCUMENT_QUESTION` | 60 / min |
| POST | `/api/v1/document-summary` (`/stream`) | `LLM_DOCUMENT_SUMMARY` | 20 / min |
| POST | `/api/v1/document-action` (`/stream`) | `LLM_DOCUMENT_ACTION` | 20 / min |
| POST | `/api/v1/document-classify` | `LLM_DOCUMENT_CLASSIFY` | 60 / min |
| POST | `/api/v1/fragment-contextualize` | `LLM_FRAGMENT_CONTEXTUALIZE` | 60 / min |
| POST | `/api/v1/graph-extraction` | `LLM_GRAPH_EXTRACTION` | 60 / min |
| POST | `/api/v1/graph-query-translation` | `LLM_GRAPH_QUERY_TRANSLATION` | 60 / min |
| POST | `/api/v1/general-chat` (`/stream`) | `LLM_GENERAL_CHAT` | 60 / min |
| POST | `/api/v1/rag-agent` (`/stream`) | `LLM_AGENT` | 20 / min |
| POST | `/api/v1/report-generate` (`/stream`) | `LLM_REPORT_GENERATE` | 60 / min |
| POST | `/api/v1/checklist-generate` (`/stream`) | `LLM_CHECKLIST_GENERATE` | 60 / min |
| POST | `/api/v1/timeline-generate` (`/stream`) | `LLM_TIMELINE_GENERATE` | 60 / min |
| POST | `/api/v1/quiz-generate` (`/stream`) | `LLM_QUIZ_GENERATE` | 60 / min |
| POST | `/api/v1/lessons-learned-generate` (`/stream`) | `LLM_LESSONS_LEARNED_GENERATE` | 60 / min |
| POST | `/api/v1/decision-brief-generate` (`/stream`) | `LLM_DECISION_BRIEF_GENERATE` | 60 / min |

---

## Default Port

| Environment | Port |
|---|---|
| Local (`.env`) | `8001` |
| Docker | `8001` |

The Swagger UI is served at `http://localhost:8001/api/docs`.
