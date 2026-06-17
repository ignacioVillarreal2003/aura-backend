# API Reference

Base URL: `http://localhost:8001/api/v1`

All endpoints except `/health` and `/ready` require authentication (see [authentication.md](authentication.md)).  
Rate-limited endpoints return `429 Too Many Requests` with a `Retry-After` header when exceeded.  
All request bodies are `application/json`.

> **Note:** the `Idempotency-Key` header mentioned for some endpoints is a
> planned feature and is **not yet implemented** — sending it currently has no
> effect (see [rate-limiting.md](rate-limiting.md#idempotency-keys)).

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
**Idempotency-Key:** supported (optional header)

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `document_ids` | `int[]` | no | max 20; attached as priority context |
| `system_prompt` | `string` | no | 1–16 000 chars; overrides the default prompt |
| `response_style` | `string` | no | 1–16 000 chars |
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

Each event is a JSON object on a `data:` line:

```
data: {"type": "progress", "step": 1, "message": "Recuperando fragmentos..."}

data: {"type": "meta", "question": "¿Cuáles son las cláusulas?", "fragments": [...]}

data: {"type": "delta", "text": "Las cláusulas "}

data: {"type": "delta", "text": "de rescisión establecen..."}

data: {"type": "complete", "result": { <DocumentQuestionResponse> }}
```

**Event types**

| `type` | Fields | Description |
|---|---|---|
| `progress` | `step: int`, `message: str` | Processing step update |
| `meta` | `question: str`, `fragments: FragmentResponse[]` | Retrieved context info |
| `delta` | `text: str` (1–50 000 chars) | Incremental answer token(s) |
| `complete` | `result: DocumentQuestionResponse` | Final full response |
| `error` | `message: str`, `code?: str` | Stream-level error |

---

## Document Summary

### POST /document-summary

Generates a summary of one or more documents identified by their IDs.

**Permission:** `LLM_DOCUMENT_SUMMARY`  
**Rate limit:** 20 / min  
**Idempotency-Key:** supported

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
| `document_ids` | `int[]` | IDs that were summarised |
| `summary` | `string` | Generated summary (1–10 000 chars) |
| `fragments` | `FragmentResponse[]` | Source fragments used |

A streaming variant `POST /document-summary/stream` (`text/event-stream`) emits
the same SSE event types described under Document Question.

---

## Document Action

### POST /document-action

Executes a free-form or templated action over one or more documents (e.g. extract key points, write an essay, compare sections).

**Permission:** `LLM_DOCUMENT_ACTION`  
**Rate limit:** 20 / min  
**Idempotency-Key:** supported

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
| `result` | `string` | LLM output (1–50 000 chars) |
| `document_ids` | `int[]` | IDs processed |
| `instruction` | `string` | Original instruction |
| `action` | `DocumentActionType?` | Action type if provided |

A streaming variant `POST /document-action/stream` (`text/event-stream`) emits
the same SSE event types described under Document Question.

---

## Document Classify

### POST /document-classify

Classifies a document by type and category based on its name and content.

**Permission:** `LLM_DOCUMENT_CLASSIFY`  
**Rate limit:** 60 / min  
**Idempotency-Key:** supported

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

## Fragment Enrich

### POST /fragment-enrich

Enriches a text fragment with a summary, extracted entities, and topics.

**Permission:** `LLM_FRAGMENT_ENRICH`  
**Rate limit:** 60 / min  
**Idempotency-Key:** supported

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `content` | `string` | yes | 1–50 000 chars, stripped, non-blank |

**Example request**
```json
{
  "content": "El artículo 5 establece que el proveedor deberá entregar el software en un plazo máximo de 90 días..."
}
```

**Response 200**

| Field | Type | Description |
|---|---|---|
| `summary` | `string` | Brief summary (1–10 000 chars) |
| `entities` | `dict[string, any]` | Key-value entity map (max 200 keys; key ≤ 255 chars; value ≤ 1 000 chars) |
| `topics` | `string[]` | List of topics (max 100; each ≤ 500 chars) |

---

## Graph Extraction

### POST /graph-extraction

Extracts named entities and their relations from a text fragment according to a provided ontology.

**Permission:** `LLM_GRAPH_EXTRACTION`  
**Rate limit:** 60 / min  
**Idempotency-Key:** supported

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
**Idempotency-Key:** supported

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
| `document_ids` | `int[]` | no | max 20; attached as priority context |
| `system_prompt` | `string` | no | 1–16 000 chars |
| `response_style` | `string` | no | 1–16 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off |
| `process_documents` | `bool` | no | process full attached documents |

**Response 200**

| Field | Type | Description |
|---|---|---|
| `messages` | `Message[]` | Full conversation history including the assistant's answer |

A streaming variant `POST /general-chat/stream` (`text/event-stream`) emits
`delta` / `complete` / `error` events.

---

## RAG Agent

### POST /rag-agent

Executes the full RAG (Retrieval-Augmented Generation) pipeline: analyses the query, retrieves document context, evaluates its sufficiency, reasons over the answer, and synthesises a final response.

**Permission:** `LLM_AGENT`  
**Rate limit:** 20 / min  
**Idempotency-Key:** supported

**Request body**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `messages` | `Message[]` | yes | 1–50 items; last message must have `role = "human"` |
| `chat_id` | `int` | yes | 1–2 147 483 647 |
| `system_prompt` | `string` | no | 1–16 000 chars |
| `response_style` | `string` | no | 1–16 000 chars |
| `retrieve_context` | `bool` | no | force RAG retrieval on/off |
| `process_documents` | `bool` | no | process full attached documents |

**Response 200**

| Field | Type | Description |
|---|---|---|
| `messages` | `Message[]` | Full conversation history including synthesised answer |

A streaming variant `POST /rag-agent/stream` (`text/event-stream`) is also available.

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
| `document_ids` | `int[]` | no | max 20; attached as priority context |
| `system_prompt` | `string` | no | 1–16 000 chars |
| `response_style` | `string` | no | 1–16 000 chars |
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
