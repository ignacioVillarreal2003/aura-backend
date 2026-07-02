# Referencia de endpoints

Base URL: `http://localhost:8000/api/v1`

Todos los endpoints salvo `/health` y `/ready` requieren autenticación Bearer (ver
[authentication.md](authentication.md)) y un permiso concreto; un token válido sin el
permiso requerido devuelve `403`. Los endpoints con límite de tasa devuelven
`429 Too Many Requests` con cabecera `Retry-After` al superarlo.

- **Rate limit estricto:** 20 req/min (operaciones de escritura y jobs).
- **Rate limit por defecto:** 60 req/min (lecturas y consultas).

Los endpoints marcados **(manage)** operan sobre cualquier documento sin exigir pertenencia
al chat y requieren un permiso administrativo `*_MANAGE`.

---

## Salud

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/health` | no | Liveness. Responde `200 {"status":"ok"}` mientras el proceso vive. |
| GET | `/ready` | no | Readiness. Verifica Redis, base de datos, RabbitMQ y almacenamiento de objetos. `200` listo / `503` degradado. |

---

## Documentos — creación

### POST /create-document
Crea un documento a partir de un archivo subido y encola su ingesta.

**Permiso:** `DOCUMENT_CREATE` · **Rate limit:** 20/min · **Content-Type:** `multipart/form-data`

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `file` | `UploadFile` | sí | Archivo del documento (tamaño y tipo validados; magic-number check) |
| `chat_id` | `int` | no | 1–2 147 483 647 |
| `prefer_docling` | `bool` | no | default `true` |
| `enrich` | `bool` | no | default `false`; clasifica y enriquece durante la ingesta |
| `graph_extract` | `bool` | no | default `false`; encola la extracción del grafo tras la ingesta |
| `name` | `string` | no | ≤ 255 chars; por defecto el nombre del archivo |

La descripción **no** se acepta al crear: se genera automáticamente en el enriquecimiento.

**Respuesta 201 — `CreateDocumentResponse`:** `id`, `name`, `mime_type`, `status` (`uploaded`), `file_size_bytes`.

### POST /bulk-create-document
Crea varios documentos en una sola solicitud. Cada archivo se procesa de forma independiente.

**Permiso:** `DOCUMENT_CREATE` · **Rate limit:** 20/min · **Content-Type:** `multipart/form-data`

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `files` | `UploadFile[]` | sí | hasta 50 archivos |
| `chat_id`, `prefer_docling`, `enrich`, `graph_extract` | | no | mismas semánticas que en `/create-document` (sin `name`) |

**Respuesta 201 — `BulkCreateDocumentResponse`:** `total`, `created`, `failed`, `items[]`.
Cada `item`: `status` (`created`\|`failed`), `filename`, y si tuvo éxito `id`, `name`, `mime_type`, `document_status`, `file_size_bytes`; si falló, `error`.

---

## Documentos — edición y restauración

### PATCH /update-document/manage/document/{document_id}
Actualiza el título de un documento. **(manage)**

**Permiso:** `DOCUMENT_UPDATE_MANAGE` · **Rate limit:** 20/min

**Body:** `{ "name": "<1–255 chars>" }` → **200 `DocumentResponse`**

### POST /restore-document/manage/document/{document_id}
Restaura un documento borrado lógicamente. **(manage)**

**Permiso:** `DOCUMENT_RESTORE_MANAGE` · **Rate limit:** 20/min → **200 `DocumentResponse`**

---

## Documentos — borrado (lógico)

| Método | Ruta | Permiso | Rate |
|---|---|---|---|
| DELETE | `/delete-document/soft/document/{document_id}` | `DOCUMENT_DELETE` | 20/min |
| DELETE | `/delete-document/soft/chat/{chat_id}` | `DOCUMENT_DELETE` | 20/min |
| DELETE | `/delete-document/manage/soft/document/{document_id}` **(manage)** | `DOCUMENT_DELETE_MANAGE` | 20/min |

Todos responden **204** sin cuerpo. Los path params son enteros ≥ 1.

---

## Documentos — consulta

### GET /document-query/manage/document/{document_id} **(manage)**
Metadatos completos de un documento. **Permiso:** `DOCUMENT_QUERY_MANAGE` · **Rate:** 60/min → **200 `DocumentResponse`**.

**`DocumentResponse`:** `id`, `chat_id?`, `name`, `description?`, `mime_type`, `status` (`uploaded`\|`processed`\|`failed`), `file_size_bytes`, `type?`, `category?`, `processing_started_at?`, `processing_finished_at?`, `created_by`, `created_at`, `updated_by?`, `updated_at?`, `deleted_by?`, `deleted_at?`.

### GET /document-query/document/{document_id}/status
Estado de procesamiento de un documento. **Permiso:** `DOCUMENT_QUERY` · **Rate:** 60/min.

### GET /document-query/manage/document/{document_id}/status **(manage)**
Igual que el anterior sin restricción de chat. **Permiso:** `DOCUMENT_QUERY_MANAGE`.

**`DocumentStatusResponse`:** `id`, `status`, `enrichment_status`, `graph_status` (`pending`\|`processed`\|`failed`\|`not_required`), `processing_started_at?`, `processing_finished_at?`.

### GET /document-query/manage/documents **(manage)**
Listado paginado y filtrado. **Permiso:** `DOCUMENT_QUERY_MANAGE` · **Rate:** 60/min.

| Query param | Tipo | Restricciones |
|---|---|---|
| `page` | `int` | ≥ 1 |
| `size` | `int` | 1–100 |
| `name` | `string` | ≤ 255 |
| `description` | `string` | ≤ 2 000 |
| `category` | `string` | ≤ 100 |
| `document_type` | `DocumentType` | `manual`\|`informe`\|`orden`\|`doctrina`\|`otro` |
| `created_from` / `created_to` | `datetime` | ISO 8601 |

**Respuesta 200 — `DocumentListResponse`:** `{ "documents": [ <DocumentResponse>, ... ] }`.

### GET /document-query/documents/chat/{chat_id}
Documentos de un chat (paginable con `page`/`size`). **Permiso:** `DOCUMENT_QUERY` · **Rate:** 60/min → **`DocumentListResponse`**.

---

## Documentos — descarga

| Método | Ruta | Permiso |
|---|---|---|
| GET | `/document-download/document/{document_id}/download` | `DOCUMENT_DOWNLOAD` |
| GET | `/document-download/manage/document/{document_id}/download` **(manage)** | `DOCUMENT_DOWNLOAD_MANAGE` |

**Rate:** 60/min. **Respuesta 200:** stream binario con `Content-Type` del archivo y
`Content-Disposition: attachment; filename="…"; filename*=UTF-8''…` (RFC 6266).

---

## Documentos — búsqueda por contenido

### POST /document-search/by-content
Busca documentos por similitud de contenido (vectorial / BM25 / híbrida).

**Permiso:** `DOCUMENT_SEARCH` · **Rate:** 60/min

**Body — `DocumentSearchRequest`:**

| Campo | Tipo | Default | Restricciones |
|---|---|---|---|
| `query` | `string` | — | 1–1 000 chars, no vacío |
| `mode` | `DocumentSearchMode` | `vector` | `vector`\|`bm25`\|`hybrid` |
| `page` | `int` | `1` | 1–200 |
| `page_size` | `int` | `10` | 1–50 |

**Respuesta 200 — `DocumentSearchListResponse`:** `results[]`, `mode`, `page`, `page_size`, `has_more`.
Cada `result`: `document` (`DocumentResponse`), `similarity` (0–1), `score`, `matched_fragments` (≥1), `best_fragment_snippet?`.

---

## Documentos — mantenimiento (jobs asíncronos, manage)

Tres pipelines con la **misma forma**: lanzar un job sobre uno, varios o todos los
documentos; consultar su estado; y detenerlo. Los jobs se ejecutan en segundo plano vía cola.

| Operación | Lanzar (POST, 20/min) | Estado (GET, 60/min) | Detener (DELETE, 20/min) | Permiso |
|---|---|---|---|---|
| Re-embedding | `/document-reembed/manage` | `/document-reembed/manage/status` | `/document-reembed/manage/stop` | `DOCUMENT_REEMBED_MANAGE` |
| Reprocesamiento | `/document-reprocess/manage` | `/document-reprocess/manage/status` | `/document-reprocess/manage/stop` | `DOCUMENT_REPROCESS_MANAGE` |
| Enriquecimiento | `/document-enrich/manage` | `/document-enrich/manage/status` | `/document-enrich/manage/stop` | `DOCUMENT_ENRICH_MANAGE` |

**Selector (en el body del POST) — `DocumentSelector`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `document_ids` | `int[]?` | IDs concretos (1 o varios, sin duplicados). Excluyente con `all_documents`. |
| `all_documents` | `bool` | Si `true`, procesa todos los documentos. Excluyente con `document_ids`. |

Debe indicarse **exactamente uno** de los dos.

- **Reembed / Enrich:** body `{ "selector": <DocumentSelector> }`.
- **Reprocess:** body `{ "selector": <DocumentSelector>, "prefer_docling": bool=true, "enrich": bool=false, "graph_extract": bool=false }`.

**Lanzar → 202 `BulkStartResponse`:** `job_id`, `operation`, `total`, `queued`.
**Estado → 200 `BulkJobStatusResponse`:** `job_id?`, `operation`, `is_running`, `stop_requested`,
`total`, `processed`, `failed`, `started_at?`, `finished_at?`, `errors[]` (`{document_id?, error}`).
**Detener → 200 `BulkJobStatusResponse`** (snapshot con `stop_requested=true`).
Un job ya en curso al relanzar devuelve `409`.

---

## Consulta de fragmentos

### POST /fragment-query/by-question
Recupera fragmentos relevantes para una o más consultas semánticas / BM25 (RAG).

**Permiso:** `FRAGMENT_QUERY` · **Rate:** 60/min

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `chat_id` | `int` | no | 1–2 147 483 647 |
| `semantic_queries` | `SemanticQuery[]` | no | máx. 10 |
| `bm25_queries` | `BM25Query[]` | no | máx. 10 |
| `rerank` | `RerankConfig` | no | ver abajo |
| `adjacent_chunks` | `int` | no | 0–3, default 1 |
| `context_expansion` | `enum` | no | `none`\|`adjacent`\|`section`, default `adjacent` |

Debe enviarse al menos una consulta (semántica o BM25).

**SemanticQuery / BM25Query:** `text` (1–16 000 chars, no vacío), `max_fragments` (1–50).
**RerankConfig:** `enabled` (bool, default `false`), `max_fragments` (1–100; requerido si `enabled=true`).

**Respuesta 200 — `FragmentListResponse`:** `fragments[]` y, con `context_expansion=section`, `groups[]`.

**`FragmentResponse`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | ID del fragmento |
| `content` | `string` | Contenido (1–50 000 chars) |
| `contextualized_content` | `string?` | Contenido contextualizado (≤ 50 000 chars) |
| `fragment_index` | `int` | Posición en el documento (0–100 000) |
| `page_number` | `int?` | Página de origen (≥ 1) |
| `section_path` | `string?` | Ruta de la sección estructural |
| `heading` | `string?` | Encabezado de la sección |
| `char_start` / `char_end` | `int?` | Offsets de caracteres (≥ 0) |
| `bbox` | `object?` | Bounding box en el documento original |
| `document` | `DocumentRef` | Documento de origen |

**`DocumentRef`:** `id`, `name`, `description?`, `type?`, `category?`.

### POST /fragment-query/by-documents
Devuelve fragmentos de una lista de documentos. Para documentos largos se
**submuestrea a un máximo de fragmentos representativos por documento** (uniforme
por índice, conservando inicio y fin), configurable vía
`FRAGMENT_QUERY_MAX_FRAGMENTS_PER_DOCUMENT` (default 50); no devuelve el total crudo.

**Permiso:** `FRAGMENT_QUERY` · **Rate:** 60/min

**Body:** `document_ids` (`int[]`, 1–50 items, cada ID 1–2 147 483 647, sin duplicados)
→ **200 `FragmentListResponse`** (mismo formato).

---

## Grafo de conocimiento

Disponible solo si el módulo está habilitado (`KNOWLEDGE_GRAPH_ENABLED=true`) y Neo4j
está accesible; en caso contrario estos endpoints devuelven `503`.

### POST /graph/query
Traduce una pregunta en lenguaje natural a una intención estructurada y la ejecuta.
**Permiso:** `GRAPH_QUERY` · **Rate:** 60/min

**Body:** `question` (1–4 000 chars, no vacío), `max_results` (1–200, default 20), `chat_id?`.

**Respuesta 200 — `GraphQueryResponse`:** `intent` (`QueryIntent`), `confidence` (0–1),
`entities[]`, `relations[]`, `nodes[]`, `explanation?`, `interpreted_as?`, `has_more`.

**`QueryIntent`:** `find_entity`, `find_neighbors`, `find_path`, `filter_by_type`, `unknown`.

### POST /graph/context
Construye contexto del grafo a partir de una pregunta o de términos.
**Permiso:** `GRAPH_QUERY` · **Rate:** 60/min

**Body — `GraphContextRequest`:** `question?` (≤ 4 000 chars), `terms[]` (hasta el máximo configurado),
`chat_id?`, `max_entities` (1–25, default 8), `max_relations` (1–100, default 30).

**Respuesta 200 — `GraphContextResponse`:** `entities[]`, `relations[]`, `facts[]`
(`{text, source_document_ids[]}`), `context_text`, `matched_terms[]`.

### GET /graph/entity/{name}
Entidad por nombre canónico con sus relaciones directas.
**Permiso:** `GRAPH_ENTITY` · **Rate:** 60/min

**Path:** `name` (1–200 chars). **Query:** `type` (`EntityType`, opcional), `depth` (1–6, default 1).

**Respuesta 200 — `GraphEntityWithRelationsResponse`:** `entity` (`GraphEntityResponse`), `relations[]` (`GraphRelationResponse`).

### GET /graph/search
Búsqueda de entidades por prefijo / palabra clave.
**Permiso:** `GRAPH_SEARCH` · **Rate:** 60/min

**Query:** `q` (1–200 chars, requerido), `type` (`EntityType`, opcional), `limit` (≥1).

**Respuesta 200 — `GraphSearchResponse`:** `results[]` (`GraphEntityResponse`), `total`, `has_more`.

### POST /graph/path
Busca caminos entre dos entidades.
**Permiso:** `GRAPH_PATH` · **Rate:** 60/min

**Body — `FindPathRequest`:** `source_name` (1–200), `target_name` (1–200, distinto del origen),
`source_type?`, `target_type?`, `max_hops` (1–6, default 4), `max_paths` (1–25, default 10),
`only_shortest` (bool, default `false`).

**Respuesta 200 — `FindPathResponse`:** `paths[]` (`GraphPath`), `truncated`.
**`GraphPath`:** `nodes[]` (2–7), `relations[]` (1–6), `length` (1–6).

### GET /graph/ontology
Ontología del grafo (tipos y límites de consulta).
**Permiso:** `GRAPH_ONTOLOGY` · **Rate:** 60/min

**Respuesta 200 — `GraphOntologyResponse`:** `entity_types[]`, `relation_types[]`, `query_max_results`, `query_max_depth`.

### GET /graph/stats/manage **(manage)**
Estadísticas globales del grafo.
**Permiso:** `GRAPH_STATS_MANAGE` · **Rate:** 60/min

**Respuesta 200 — `GraphStatsResponse`:** `total_entities`, `total_relations`, `entities_by_type` (dict), `total_documents_indexed`.

### Extracción del grafo (job asíncrono, manage)
Mismo patrón que los pipelines de mantenimiento. **Permiso:** `GRAPH_EXTRACT_MANAGE`.

| Acción | Método | Ruta | Rate |
|---|---|---|---|
| Lanzar | POST | `/graph/extraction/manage` | 20/min |
| Estado | GET | `/graph/extraction/manage/status` | 60/min |
| Detener | DELETE | `/graph/extraction/manage/stop` | 20/min |

**Body del POST — `GraphReextractRequest`:** `{ "selector": <DocumentSelector> }`.
**Lanzar → 202 `BulkStartResponse`**, **estado/detener → `BulkJobStatusResponse`** (ver mantenimiento).

**Tipos compartidos del grafo**

`GraphEntityResponse`: `canonical_name` (1–200), `display_name` (1–200), `type` (`EntityType`),
`aliases[]` (máx. 20), `description?` (≤ 2 000), `source_document_ids[]`, `created_at?`, `updated_at?`.

`GraphRelationResponse`: `type` (1–64), `source`/`target` (`GraphRelationEndpoint`), `confidence` (0–1),
`source_document_ids[]`, `created_at?`, `updated_at?`.
`GraphRelationEndpoint`: `canonical_name`, `display_name`, `type`.

`EntityType`: `person`, `organization`, `location`, `product`, `event`, `concept`, `date`, `other`.

---

## Respuestas de error comunes

Todos los errores comparten el mismo envelope (incluidos los del middleware de autenticación):

```json
{
  "error": "CódigoDeError",
  "message": "Descripción legible",
  "request_id": "uuid-opcional"
}
```

La cabecera `X-Request-ID` acompaña la respuesta para correlación. Los errores de
validación (422) añaden un campo `detail`:

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "detail": [
    { "loc": ["body", "document_ids", 0], "msg": "…", "type": "value_error" }
  ]
}
```

| Código | Cuándo ocurre |
|---|---|
| 400 | Solicitud inválida o regla de negocio básica |
| 401 | Sin credenciales o token inválido/expirado |
| 403 | Credenciales válidas pero permisos insuficientes |
| 404 | Recurso no encontrado |
| 409 | Conflicto (p. ej. un job ya en curso) |
| 413 | Archivo demasiado grande |
| 415 | Tipo de archivo no soportado |
| 422 | Fallo de validación |
| 429 | Límite de tasa superado (ver `Retry-After`) |
| 500 | Error interno no controlado |
| 502 | Dependencia externa (LLM, servicio) devolvió error |
| 503 | Servicio o dependencia no disponible |
