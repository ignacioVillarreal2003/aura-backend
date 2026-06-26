# API Reference

Base URL: `http://localhost:8001/api/v1`

All endpoints except `/health` and `/ready` require authentication (see [authentication.md](authentication.md)).  
Rate-limited endpoints return `429 Too Many Requests` with a `Retry-After` header when exceeded.  
All request bodies are `application/json`.

> **Note:** the `Idempotency-Key` header is a planned feature and is **not yet
> implemented** — sending it currently has no effect (see
> [rate-limiting.md](rate-limiting.md#idempotency-keys)).
>
> **SSE streaming:** every `/stream` endpoint emits `progress` events whose
> `message` field is human-readable Spanish and whose `step` field is a stable
> machine id — render `message`, not `step`.

---

## Health

### GET /health

Liveness probe. Always returns 200 while the process is running.

**No authentication required.**

**Response 200**
```json
{ "status": "ok" }
```

---

### GET /ready

Readiness probe. Checks the shared HTTP client, the Ollama LLM and Redis. Each
dependency check has a short per-dependency timeout, so a hung dependency turns
into a fast `503` instead of stalling the probe.

**No authentication required.**

**Response 200** — every dependency healthy.
```json
{
  "status": "ok",
  "checks": {
    "http_client": { "status": "healthy" },
    "ollama": { "status": "ok", "tools_bound": true },
    "redis": { "status": "ok" }
  }
}
```

**Response 503** — at least one dependency is unavailable (`status: "degraded"`).
Each entry's `status` is one of `ok`/`healthy`, `error` (failed or timed out) or
`not_configured` (not initialised at startup).
```json
{
  "status": "degraded",
  "checks": {
    "http_client": { "status": "healthy" },
    "ollama": { "status": "error", "tools_bound": false },
    "redis": { "status": "ok" }
  }
}
```

---

## Document Question

### POST /document-question

Answers a question based on retrieved document fragments.

**Permission:** `LLM_DOCUMENT_QUESTION`  
**Rate limit:** 60 / min

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `document_ids` | `int[]` | no | max 50; attached as priority context (only loaded when `process_documents` is true) |
| `system_prompt` | `string` | no | 1–10 000 chars; overrides the default prompt |
| `response_style` | `string` | no | 1–10 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off; omit for service default |
| `process_documents` | `bool` | no | process full attached documents; omit for service default |

**Message object**

| Field | Type | Constraints |
|---|---|---|
| `role` | `"human"` \| `"assistant"` | required |
| `content` | `string` | 1–16 000 chars, stripped, non-blank |

**Example request**
```json
{
  "messages": [
    { "role": "human", "content": "¿Cuáles son las cláusulas de rescisión?" }
  ],
  "chat_id": 7
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `question` | `string` | Extracted question (1–16 000 chars) |
| `answer` | `string` | LLM answer (1–50 000 chars) |
| `messages` | `Message[]` | Full conversation including answer |
| `fragments` | `FragmentResponse[]` | Source fragments used (may be empty) |

```json
{
  "question": "¿Cuáles son las cláusulas de rescisión?",
  "answer": "Las cláusulas de rescisión establecen que...",
  "messages": [
    { "role": "human",     "content": "¿Cuáles son las cláusulas de rescisión?" },
    { "role": "assistant", "content": "Las cláusulas de rescisión establecen que..." }
  ],
  "fragments": [{ "id": 12, "content": "...", "document_id": 3 }]
}
```

---

### POST /document-question/stream

Same as `/document-question` but streams the answer as [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events).

**Permission:** `LLM_DOCUMENT_QUESTION` (same as the base endpoint)  
**Rate limit:** 20 / min  
**Response content-type:** `text/event-stream`

Each event is a JSON object on a `data:` line. Every stream starts with an
initial `processing` progress event, then emits a `progress` event before each
pipeline stage:

```
data: {"type": "progress", "step": "processing", "message": "Procesando tu consulta..."}

data: {"type": "progress", "step": "reformulating", "message": "Interpretando y optimizando la consulta..."}

data: {"type": "progress", "step": "searching", "message": "Buscando información relevante en los documentos..."}

data: {"type": "meta", "question": "¿Cuáles son las cláusulas?", "fragments": [...]}

data: {"type": "delta", "text": "Las cláusulas "}

data: {"type": "delta", "text": "de rescisión establecen..."}

data: {"type": "complete", "result": { <DocumentQuestionResponse> }}
```

**Event types**

| `type` | Fields | Description |
|---|---|---|
| `progress` | `step: str`, `message: str` | Pipeline-stage update. `step` is a machine id (e.g. `processing`, `reformulating`, `searching`, `reducing`, `generation`); `message` is the human-readable Spanish text — display `message`, not `step`. |
| `meta` | `question: str`, `fragments: FragmentResponse[]` | Retrieved context info (document-question only) |
| `delta` | `text: str` (1–50 000 chars) | Incremental answer token(s) |
| `complete` | `result: DocumentQuestionResponse` | Final full response |
| `error` | `message: str`, `code?: str` | Stream-level error |

---

## Document Summary

### POST /document-summary

Generates a summary of one or more documents identified by their IDs.

**Permission:** `LLM_DOCUMENT_SUMMARY`  
**Rate limit:** 20 / min  
**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `document_ids` | `int[]` | yes | 1–50 items; each ID 1–2 147 483 647; no duplicates |
| `chat_id` | `int` | yes | 1–2 147 483 647 (informative; context comes from `document_ids`) |

**Example request**
```json
{
  "document_ids": [1, 5, 12],
  "chat_id": 7
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `title` | `string` | Short title (may be empty; ≤ 100 chars) |
| `description` | `string` | Short description (may be empty; ≤ 1 000 chars) |
| `summary` | `string` | Generated summary (1–10 000 chars) |
| `fragments` | `FragmentResponse[]` | Source fragments used |
| `degraded_stages` | `string[]` | Context-pipeline stages that degraded (empty when none); a non-empty list means the answer may be partial |

A streaming variant `POST /document-summary/stream` (`text/event-stream`) emits
`progress` / `complete` / `error` events.

---

## Document Action

### POST /document-action

Executes a free-form or templated action over one or more documents (e.g. extract key points, write an essay, compare sections).

**Permission:** `LLM_DOCUMENT_ACTION`  
**Rate limit:** 20 / min  
**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `document_ids` | `int[]` | yes | 1–50 items; each ID 1–2 147 483 647; no duplicates |
| `instruction` | `string` | yes | 1–10 000 chars, stripped, non-blank |
| `action` | `DocumentActionType` | no | See values below; inferred from the instruction if omitted |
| `chat_id` | `int` | yes | 1–2 147 483 647 (informative; context comes from `document_ids`) |

**DocumentActionType values**

| Value | Description |
|---|---|
| `summarize` | Summarise the documents |
| `essay` | Write an essay based on the content |
| `key_points` | Extract key points |
| `compare` | Compare documents |
| `analyze` | Analyse the content |
| `explain` | Explain the content |
| `report` | Generate a structured report |

**Example request**
```json
{
  "document_ids": [3, 7],
  "instruction": "Compara las cláusulas de confidencialidad de ambos contratos.",
  "action": "compare",
  "chat_id": 7
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `title` | `string` | Short title (may be empty; ≤ 100 chars) |
| `description` | `string` | Short description (may be empty; ≤ 1 000 chars) |
| `result` | `string` | LLM output (1–50 000 chars) |
| `instruction` | `string` | Original instruction |
| `action` | `DocumentActionType?` | Action type if provided |
| `fragments` | `FragmentResponse[]` | Source fragments used |
| `degraded_stages` | `string[]` | Context-pipeline stages that degraded (empty when none) |

A streaming variant `POST /document-action/stream` (`text/event-stream`) emits
`progress` / `delta` / `complete` / `error` events.

---

## Document Classify

### POST /document-classify

Classifies a document by type and category based on its name and content.

**Permission:** `LLM_DOCUMENT_CLASSIFY`  
**Rate limit:** 60 / min  
**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `document_name` | `string` | yes | 1–255 chars, stripped, non-blank |
| `content` | `string` | yes | 1–50 000 chars, stripped, non-blank |

**Example request**
```json
{
  "document_name": "Contrato_Gamma_2024.pdf",
  "content": "CONTRATO DE PRESTACIÓN DE SERVICIOS\n\nEntre la empresa GAMMA CORP..."
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `type` | `DocumentType` | Classified type (see values below) |
| `category` | `string` | Category label (1–100 chars) |
| `description` | `string` | Short explanation (1–2 000 chars) |

**DocumentType values:** `manual`, `informe`, `orden`, `doctrina`, `otro`

---

## Fragment Contextualize

### POST /fragment-contextualize

Generates a short contextual prefix for a fragment, given the parent document's
summary — used to improve retrieval (contextual embeddings).

**Permission:** `LLM_FRAGMENT_CONTEXTUALIZE`  
**Rate limit:** 60 / min

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `document_summary` | `string` | yes | 1–2 000 chars, stripped, non-blank |
| `content` | `string` | yes | 1–50 000 chars, stripped, non-blank |

**Example request**
```json
{
  "document_summary": "Contrato de prestación de servicios entre GAMMA CORP y un proveedor de software.",
  "content": "El artículo 5 establece que el proveedor deberá entregar el software en un plazo máximo de 90 días."
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `context` | `string` | Contextual prefix for the fragment (1–2 000 chars) |

---

## Graph Extraction

### POST /graph-extraction

Extracts named entities and their relations from a text fragment according to a provided ontology.

**Permission:** `LLM_GRAPH_EXTRACTION`  
**Rate limit:** 60 / min  
**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `content` | `string` | yes | 1–50 000 chars |
| `document_id` | `int` | yes | 1–2 147 483 647 |
| `fragment_id` | `int` | yes | 1–2 147 483 647 |
| `allowed_entity_types` | `string[]` | yes | 1–64 types; each ≤ 64 chars, non-blank |
| `allowed_relation_types` | `string[]` | no | max 128 types; each ≤ 64 chars |
| `max_entities` | `int` | no | 1–50, default `50` |
| `max_relations` | `int` | no | 0–100, default `100` |

**Example request**
```json
{
  "content": "GAMMA CORP firmó un contrato con Juan Pérez en Buenos Aires.",
  "document_id": 3,
  "fragment_id": 17,
  "allowed_entity_types": ["PERSON", "ORGANIZATION", "LOCATION"],
  "allowed_relation_types": ["FIRMÓ_CONTRATO_CON", "UBICADO_EN"],
  "max_entities": 10,
  "max_relations": 20
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `entities` | `ExtractedEntity[]` | Extracted entities (max 50) |
| `relations` | `ExtractedRelation[]` | Extracted relations (max 100) |

**ExtractedEntity**

| Field | Type | Constraints |
|---|---|---|
| `name` | `string` | 1–200 chars, non-blank |
| `type` | `EntityType` | See values below |
| `aliases` | `string[]` | max 20; each ≤ 200 chars |
| `description` | `string?` | max 2 000 chars |

**EntityType values:** `person`, `organization`, `location`, `product`, `event`, `concept`, `date`, `other`

**ExtractedRelation**

| Field | Type | Constraints |
|---|---|---|
| `type` | `string` | 1–64 chars, non-blank |
| `source` | `{ name: string, type: EntityType }` | Source entity reference |
| `target` | `{ name: string, type: EntityType }` | Target entity reference (must differ from source) |
| `confidence` | `float` | 0.0–1.0, default `0.5` |

---

## Graph Query Translation

### POST /graph-query-translation

Translates a natural-language question into a structured graph query intent.

**Permission:** `LLM_GRAPH_QUERY_TRANSLATION`  
**Rate limit:** 60 / min  
**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `question` | `string` | yes | 1–4 000 chars, non-blank |
| `ontology` | `GraphOntology` | yes | See below |

**GraphOntology**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `entity_types` | `string[]` | yes | 1–64 types; each ≤ 64 chars, non-blank |
| `relation_types` | `string[]` | no | max 128 types; each ≤ 64 chars |

**Example request**
```json
{
  "question": "¿Quién firmó el contrato con Gamma Corp?",
  "ontology": {
    "entity_types": ["PERSON", "ORGANIZATION"],
    "relation_types": ["FIRMÓ_CONTRATO_CON"]
  }
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `intent` | `QueryIntent` | Detected query intent |
| `parameters` | `dict[string, any]` | Intent-specific parameters (max 32 keys) |
| `confidence` | `float` | Confidence score 0.0–1.0 |
| `reasoning` | `string?` | Explanation (max 2 000 chars) |

**QueryIntent values**

| Value | Description |
|---|---|
| `find_entity` | Look up a specific entity |
| `find_neighbors` | Find entities related to a given entity |
| `find_path` | Find a path between two entities |
| `filter_by_type` | Filter entities by type |
| `unknown` | Intent could not be determined |

---

## General Chat

### POST /general-chat

General-purpose assistant chat. Unlike the RAG endpoints it does not run a
retrieval pipeline by default — it answers from the conversation history (plus
any explicitly attached documents).

**Permission:** `LLM_GENERAL_CHAT`  
**Rate limit:** 60 / min (`/general-chat`), 20 / min (`/general-chat/stream`)

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `document_ids` | `int[]` | no | max 50; attached as priority context (only loaded when `process_documents` is true) |
| `system_prompt` | `string` | no | 1–10 000 chars |
| `response_style` | `string` | no | 1–10 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off |
| `process_documents` | `bool` | no | process full attached documents |

**Response 200**

| Field | Type | Description |
|---|---|---|
| `answer` | `string` | LLM answer (1–50 000 chars) |
| `messages` | `Message[]` | Full conversation history including the assistant's answer |
| `fragments` | `FragmentResponse[]` | Source fragments used (empty unless retrieval/attachment ran) |
| `degraded_stages` | `string[]` | Context-pipeline stages that degraded (empty when none) |

A streaming variant `POST /general-chat/stream` (`text/event-stream`) emits
`progress` / `delta` / `complete` / `error` events.

---

## RAG Agent

### POST /rag-agent

Executes the full RAG (Retrieval-Augmented Generation) pipeline as a LangGraph
workflow: analyses the query, retrieves graph + document context, **grades the
context's sufficiency and (if weak) refines the query and re-retrieves** a
bounded number of times (Corrective-RAG), synthesises the answer, and runs an
answer guardrail before returning.

**Permission:** `LLM_AGENT`  
**Rate limit:** 20 / min

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `system_prompt` | `string` | no | 1–10 000 chars |
| `response_style` | `string` | no | 1–10 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off |
| `process_documents` | `bool` | no | process full attached documents |

> The agent request has **no** `document_ids` field.

**Response 200**

| Field | Type | Description |
|---|---|---|
| `messages` | `Message[]` | Conversation with the synthesised assistant answer |
| `fragments` | `FragmentResponse[]` | Source fragments used (may be empty) |

### POST /rag-agent/stream

Streaming variant (`text/event-stream`). Emits an initial `processing` event,
then a `progress` event **before each pipeline node runs** (real-time status),
then a `complete` (or `error`).

```
data: {"type": "progress", "step": "processing", "message": "Procesando tu consulta..."}

data: {"type": "progress", "step": "query_analyzer", "message": "Analizando y reformulando la consulta..."}

data: {"type": "progress", "step": "context_retriever", "message": "Buscando información relevante en los documentos..."}

data: {"type": "progress", "step": "context_grader", "message": "Evaluando si el contexto recuperado es suficiente..."}

data: {"type": "complete", "result": { <AgentResponse> }}
```

`step` is the node id; possible values: `processing`, `query_analyzer`,
`graph_context_retriever`, `context_retriever`, `document_fetcher`,
`context_grader`, `query_refiner`, `answer_synthesizer`, `guardrails`,
`fallback`. As everywhere, display `message` (Spanish), not `step`.

---

## Structured Generation

Six endpoints turn an operational input into a structured military document.
They share one request contract and differ only in the document they produce
(and, for reports, a `report_type`). Each also exposes a `/stream` SSE variant.

| Endpoint | Produces | Permission |
|---|---|---|
| `POST /report-generate` | Standardised report (SITREP / INTSUM / OPORD) | `LLM_REPORT_GENERATE` |
| `POST /checklist-generate` | Interactive checklist from a procedure | `LLM_CHECKLIST_GENERATE` |
| `POST /timeline-generate` | Chronology of events from a narrative | `LLM_TIMELINE_GENERATE` |
| `POST /quiz-generate` | Evaluation quiz from training material | `LLM_QUIZ_GENERATE` |
| `POST /lessons-learned-generate` | After-action lessons-learned analysis | `LLM_LESSONS_LEARNED_GENERATE` |
| `POST /decision-brief-generate` | Executive decision brief | `LLM_DECISION_BRIEF_GENERATE` |

**Rate limit:** 60 / min (base endpoint), 20 / min (`/stream` variant)

**Shared request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `report_type` | `"SITREP"` \| `"INTSUM"` \| `"OPORD"` | report only | required by `/report-generate` |
| `document_ids` | `int[]` | no | max 50; attached as priority context (only loaded when `process_documents` is true) |
| `system_prompt` | `string` | no | 1–10 000 chars |
| `response_style` | `string` | no | 1–10 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off |
| `process_documents` | `bool` | no | process full attached documents |

**Example request** (`POST /report-generate`)
```json
{
  "report_type": "SITREP",
  "messages": [
    { "role": "human", "content": "Patrulla en sector norte sin novedad entre 0600 y 1200." }
  ],
  "chat_id": 7
}
```

**Response 200** — endpoint-specific. Reports return `report_type`, `content`
(markdown), `messages`, `fragments` and `degraded_stages`; the other endpoints
return their structured payload plus `messages`/`fragments`. See the Swagger UI
(`/api/docs`) for the exact response model of each endpoint.

**Streaming variants** (`/…-generate/stream`, `text/event-stream`) emit
`progress` / `complete` / `error` events.

---

## Common Error Responses

All error responses share this envelope:

```json
{
  "error": "ErrorCodeHere",
  "message": "Human-readable description",
  "request_id": "optional-uuid"
}
```

Validation errors (422) include an additional `detail` array:

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "detail": [
    {
      "loc": ["body", "messages", 0, "content"],
      "msg": "Value error, content must not be blank",
      "type": "value_error"
    }
  ]
}
```

| HTTP Status | When |
|---|---|
| 400 | Malformed request or business rule violation |
| 401 | Missing or invalid authentication credentials |
| 403 | Valid credentials but insufficient permissions |
| 422 | Pydantic validation failure |
| 429 | Rate limit exceeded |
| 500 | Unhandled internal error |
| 502 | Upstream service (Ollama / external HTTP) returned an error |
| 503 | Required service not available (Ollama down, service not initialised) |
