# Referencia de endpoints

Base URL: `http://localhost:8001/api/v1`

Todos los endpoints salvo `/health` y `/ready` requieren autenticación (ver [authentication.md](authentication.md)).  
Los endpoints con límite de tasa devuelven `429 Too Many Requests` con cabecera `Retry-After` al superarlo.

---

## Salud

### GET /health

Prueba de vivacidad. Responde siempre 200 mientras el proceso está en marcha.

**Sin autenticación.**

```json
{ "status": "ok" }
```

---

### GET /ready

Prueba de preparación. Verifica que Redis y la base de datos estén disponibles.

**Sin autenticación.**

**200** — servicio listo.  
**503** — alguna dependencia no está disponible.

---

## Documentos

### POST /create-document

Crea un documento a partir de un archivo subido.

**Autenticación:** requerida  
**Rate limit:** 20 / min  
**Idempotency-Key:** soportado (cabecera opcional)  
**Content-Type:** `multipart/form-data`

**Campos del formulario**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `file` | `UploadFile` | sí | Archivo del documento |
| `chat_id` | `int` | no | 1–2 147 483 647 |
| `prefer_docling` | `bool` | no | default `false`; usa el pipeline Docling en vez del predeterminado |

**Ejemplo**

```http
POST /api/v1/create-document
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="file"; filename="contrato.pdf"
Content-Type: application/pdf

<bytes>
--boundary
Content-Disposition: form-data; name="chat_id"

7
--boundary--
```

**Respuesta 201**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | ID asignado al documento |
| `name` | `string` | Nombre del archivo (1–255 chars) |
| `mime_type` | `string` | MIME type detectado (1–64 chars) |
| `status` | `string` | Estado inicial (`uploaded`) |
| `file_size_bytes` | `int` | Tamaño en bytes (≥ 1) |

---

### DELETE /delete-document/soft/document/{document_id}

Borrado lógico de un documento.

**Autenticación:** requerida  
**Rate limit:** 20 / min

**Path params**

| Param | Tipo | Restricciones |
|---|---|---|
| `document_id` | `int` | ≥ 1 |

**Respuesta 204** — sin cuerpo.

---

### DELETE /delete-document/soft/chat/{chat_id}

Borrado lógico de todos los documentos asociados a un chat.

**Autenticación:** requerida  
**Rate limit:** 20 / min

**Path params**

| Param | Tipo | Restricciones |
|---|---|---|
| `chat_id` | `int` | ≥ 1 |

**Respuesta 204** — sin cuerpo.

---

### GET /document-query/document/{document_id}

Devuelve los metadatos completos de un documento.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | ID del documento |
| `chat_id` | `int?` | Chat al que pertenece |
| `name` | `string` | Nombre (1–255 chars) |
| `description` | `string?` | Descripción (1–2 000 chars) |
| `mime_type` | `string` | MIME type (1–64 chars) |
| `status` | `string` | `uploaded` \| `processed` \| `failed` |
| `file_size_bytes` | `int` | Tamaño en bytes |
| `type` | `string?` | Tipo clasificado (≤ 64 chars) |
| `category` | `string?` | Categoría (1–100 chars) |
| `processing_started_at` | `datetime?` | Inicio del procesamiento |
| `processing_finished_at` | `datetime?` | Fin del procesamiento |
| `created_by` | `int` | ID del usuario creador |
| `created_at` | `datetime` | Fecha de creación |
| `updated_by` | `int?` | ID del último editor |
| `updated_at` | `datetime?` | Fecha de última edición |
| `deleted_by` | `int?` | ID del usuario que lo borró |
| `deleted_at` | `datetime?` | Fecha de borrado lógico |

---

### GET /document-query/documents

Listado paginado y filtrado de documentos.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Query params**

| Param | Tipo | Default | Restricciones |
|---|---|---|---|
| `page` | `int` | `1` | ≥ 1 |
| `size` | `int` | `1` | 1–100 |
| `name` | `string` | — | ≤ 255 chars |
| `description` | `string` | — | ≤ 2 000 chars |
| `category` | `string` | — | ≤ 100 chars |
| `document_type` | `DocumentType` | — | `manual` \| `informe` \| `orden` \| `doctrina` \| `otro` |
| `created_from` | `datetime` | — | ISO 8601 |
| `created_to` | `datetime` | — | ISO 8601 |

**Respuesta 200**

```json
{
  "documents": [ <DocumentResponse>, ... ]
}
```

---

### GET /document-query/documents/chat/{chat_id}

Devuelve todos los documentos asociados a un chat.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Respuesta 200** — mismo formato que el listado (`DocumentListResponse`).

---

### GET /document-download/document/{document_id}/download

Descarga el archivo binario de un documento.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Respuesta 200**

- `Content-Type`: MIME type del archivo almacenado
- `Content-Disposition`: `attachment; filename="<nombre>"`
- Cuerpo: bytes del archivo

---

## Post-procesado de documentos

Permite iniciar, consultar y detener el pipeline de post-procesado (embeddings, enriquecimiento, extracción de grafo) sobre documentos ya ingestados.

### POST /post-process-document/start

Inicia o reanuda el post-procesado para **todos** los documentos pendientes.

**Autenticación:** requerida  
**Rate limit:** 20 / min  
**Idempotency-Key:** soportado  
**Sin cuerpo.**

**Respuesta 202**

| Campo | Tipo | Descripción |
|---|---|---|
| `message` | `string` | Mensaje descriptivo (1–500 chars) |
| `total_documents` | `int` | Documentos encolados (≥ 0) |
| `job_id` | `string?` | ID del trabajo iniciado (≤ 64 chars) |

---

### POST /post-process-document/documents

Inicia o reanuda el post-procesado para una lista específica de documentos.

**Autenticación:** requerida  
**Rate limit:** 20 / min  
**Idempotency-Key:** soportado

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `document_ids` | `int[]` | sí | 1–10 000 items; cada ID 1–2 147 483 647; sin duplicados |

**Respuesta 202** — mismo formato que `/start`.

---

### GET /post-process-document/status

Estado actual del post-procesado.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `job_id` | `string?` | ID del trabajo activo |
| `is_running` | `bool` | Si el proceso está activo |
| `total_documents` | `int` | Total de documentos en el trabajo |
| `processed_documents` | `int` | Documentos completados |
| `failed_documents` | `int` | Documentos fallidos |
| `current_document_id` | `int?` | ID del documento en curso (solo si `is_running`) |
| `started_at` | `datetime?` | Inicio del trabajo |
| `finished_at` | `datetime?` | Fin del trabajo (ausente si `is_running`) |
| `errors` | `PostProcessDocumentError[]` | Errores registrados (máx. 1 000) |

**PostProcessDocumentError**

| Campo | Tipo | Descripción |
|---|---|---|
| `document_id` | `int` | ID del documento que falló |
| `error` | `string` | Mensaje de error (1–500 chars) |

---

### DELETE /post-process-document/stop

Detiene el post-procesado activo.

**Autenticación:** requerida  
**Rate limit:** 20 / min

**Respuesta 204** — sin cuerpo.

---

## Post-procesado de fragmentos

Misma estructura que el post-procesado de documentos pero opera sobre fragmentos extraídos.

### POST /post-process-fragment/start

Inicia o reanuda el enriquecimiento para **todos** los fragmentos pendientes.

**Autenticación:** requerida  
**Rate limit:** 20 / min  
**Idempotency-Key:** soportado  
**Sin cuerpo.**

**Respuesta 202**

| Campo | Tipo | Descripción |
|---|---|---|
| `message` | `string` | Mensaje descriptivo (1–500 chars) |
| `total_fragments` | `int` | Fragmentos encolados (≥ 0) |
| `job_id` | `string?` | ID del trabajo iniciado (≤ 64 chars) |

---

### POST /post-process-fragment/documents

Inicia el enriquecimiento para fragmentos de una lista de documentos.

**Autenticación:** requerida  
**Rate limit:** 20 / min  
**Idempotency-Key:** soportado

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `document_ids` | `int[]` | sí | 1–500 items; cada ID 1–2 147 483 647; sin duplicados |

**Respuesta 202** — mismo formato que `/start`.

---

### GET /post-process-fragment/status

Estado actual del enriquecimiento de fragmentos.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `job_id` | `string?` | ID del trabajo activo |
| `is_running` | `bool` | Si el proceso está activo |
| `total_fragments` | `int` | Total de fragmentos |
| `processed_fragments` | `int` | Fragmentos completados |
| `failed_fragments` | `int` | Fragmentos fallidos |
| `current_fragment_id` | `int?` | ID del fragmento en curso (solo si `is_running`) |
| `started_at` | `datetime?` | Inicio del trabajo |
| `finished_at` | `datetime?` | Fin del trabajo (ausente si `is_running`) |
| `errors` | `PostProcessFragmentError[]` | Errores registrados (máx. 1 000) |

---

### DELETE /post-process-fragment/stop

Detiene el enriquecimiento activo.

**Autenticación:** requerida  
**Rate limit:** 20 / min

**Respuesta 204** — sin cuerpo.

---

## Consulta de fragmentos

### POST /fragment-query/by-question

Recupera fragmentos relevantes para una o más consultas semánticas / BM25. Diseñado para escenarios de RAG.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `chat_id` | `int` | no | 1–2 147 483 647 |
| `semantic_queries` | `SemanticQuery[]` | no | máx. 10 |
| `bm25_queries` | `BM25Query[]` | no | máx. 10 |
| `rerank` | `RerankConfig` | no | ver abajo |

**SemanticQuery / BM25Query**

| Campo | Tipo | Restricciones |
|---|---|---|
| `text` | `string` | 1–16 000 chars, no vacío |
| `max_fragments` | `int` | 1–50 |

**RerankConfig**

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `enabled` | `bool` | `false` | Activa reranking sobre los fragmentos recuperados |
| `max_fragments` | `int?` | — | 1–100; fragmentos devueltos tras reranking |

**Respuesta 200**

```json
{
  "fragments": [ <FragmentResponse>, ... ]
}
```

**FragmentResponse**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | ID del fragmento |
| `content` | `string` | Contenido (1–50 000 chars) |
| `fragment_index` | `int` | Posición dentro del documento (0–100 000) |
| `summary` | `string?` | Resumen enriquecido (1–50 000 chars) |
| `entities` | `dict?` | Entidades extraídas (máx. 200 claves; clave ≤ 255 chars; valor ≤ 1 000 chars) |
| `topics` | `string[]?` | Temas (máx. 100; cada uno ≤ 500 chars) |
| `document` | `DocumentRef` | Documento de origen |

**DocumentRef (anidado en FragmentResponse)**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `int` | ID del documento |
| `name` | `string` | Nombre (1–255 chars) |
| `description` | `string?` | Descripción (1–2 000 chars) |
| `type` | `string?` | Tipo clasificado (≤ 64 chars) |
| `category` | `string?` | Categoría (1–100 chars) |

---

### POST /fragment-query/by-documents

Devuelve todos los fragmentos almacenados para una lista de documentos.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `document_ids` | `int[]` | sí | 1–50 items; cada ID 1–2 147 483 647; sin duplicados |

**Respuesta 200** — mismo formato `FragmentListResponse` que `/by-question`.

---

## Grafo de conocimiento

### POST /graph/query

Traduce una pregunta en lenguaje natural a una intención estructurada y la ejecuta sobre Neo4j.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `question` | `string` | sí | 1–4 000 chars, no vacío |
| `max_results` | `int` | no | 1–200, default `20` |
| `chat_id` | `int` | no | 1–2 147 483 647 |

**Ejemplo**

```json
{
  "question": "¿Quién firmó el contrato con Gamma Corp?",
  "max_results": 10
}
```

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `intent` | `QueryIntent` | Intención detectada (ver valores) |
| `confidence` | `float` | Confianza 0.0–1.0 |
| `entities` | `GraphEntityResponse[]` | Entidades encontradas (máx. 200) |
| `relations` | `GraphRelationResponse[]` | Relaciones encontradas (máx. 200) |
| `explanation` | `string?` | Explicación del razonamiento (≤ 2 000 chars) |

**QueryIntent**

| Valor | Descripción |
|---|---|
| `find_entity` | Búsqueda de una entidad concreta |
| `find_neighbors` | Entidades relacionadas con una entidad dada |
| `find_path` | Camino entre dos entidades |
| `filter_by_type` | Filtrado de entidades por tipo |
| `unknown` | Intención no determinada |

**GraphEntityResponse**

| Campo | Tipo | Descripción |
|---|---|---|
| `canonical_name` | `string` | Nombre canónico (1–200 chars) |
| `display_name` | `string` | Nombre de visualización (1–200 chars) |
| `type` | `EntityType` | Tipo de entidad (ver valores) |
| `aliases` | `string[]` | Alias (máx. 20) |
| `description` | `string?` | Descripción (≤ 2 000 chars) |
| `source_document_ids` | `int[]` | IDs de documentos de origen |
| `created_at` | `datetime?` | Fecha de creación |
| `updated_at` | `datetime?` | Fecha de actualización |

**GraphRelationResponse**

| Campo | Tipo | Descripción |
|---|---|---|
| `type` | `string` | Tipo de relación (1–64 chars) |
| `source` | `GraphRelationEndpoint` | Entidad de origen |
| `target` | `GraphRelationEndpoint` | Entidad de destino |
| `confidence` | `float` | Confianza 0.0–1.0 |
| `source_document_ids` | `int[]` | IDs de documentos de origen |
| `created_at` | `datetime?` | Fecha de creación |
| `updated_at` | `datetime?` | Fecha de actualización |

**GraphRelationEndpoint**

| Campo | Tipo | Descripción |
|---|---|---|
| `canonical_name` | `string` | Nombre canónico (1–200 chars) |
| `display_name` | `string` | Nombre de visualización (1–200 chars) |
| `type` | `EntityType` | Tipo de entidad |

**EntityType**

| Valor |
|---|
| `person` |
| `organization` |
| `location` |
| `product` |
| `event` |
| `concept` |
| `date` |
| `other` |

---

### GET /graph/entity/{name}

Devuelve una entidad por su nombre canónico junto con sus relaciones directas hasta la profundidad indicada.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Path params**

| Param | Tipo | Restricciones |
|---|---|---|
| `name` | `string` | 1–200 chars |

**Query params**

| Param | Alias HTTP | Tipo | Default | Restricciones |
|---|---|---|---|---|
| `entity_type` | `type` | `EntityType` | — | Uno de los valores de EntityType |
| `depth` | `depth` | `int` | `1` | 1–6 |

**Ejemplo**

```
GET /api/v1/graph/entity/Gamma%20Corp?type=organization&depth=2
```

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `entity` | `GraphEntityResponse` | Entidad encontrada |
| `relations` | `GraphRelationResponse[]` | Relaciones hasta `depth` saltos (máx. 200) |

---

### POST /graph/path

Busca caminos entre dos entidades en el grafo.

**Autenticación:** requerida  
**Rate limit:** 60 / min

**Request body**

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `source_name` | `string` | sí | 1–200 chars, no vacío |
| `target_name` | `string` | sí | 1–200 chars, no vacío; distinto de `source_name` |
| `source_type` | `EntityType` | no | Tipo de la entidad de origen |
| `target_type` | `EntityType` | no | Tipo de la entidad de destino |
| `max_hops` | `int` | no | 1–6, default `4` |
| `max_paths` | `int` | no | 1–25, default `10` |
| `only_shortest` | `bool` | no | default `false`; si `true` devuelve solo el camino más corto |

**Ejemplo**

```json
{
  "source_name": "Juan Pérez",
  "target_name": "Gamma Corp",
  "max_hops": 3,
  "only_shortest": true
}
```

**Respuesta 200**

| Campo | Tipo | Descripción |
|---|---|---|
| `paths` | `GraphPath[]` | Caminos encontrados (máx. 25) |
| `truncated` | `bool` | `true` si hay más caminos de los devueltos |

**GraphPath**

| Campo | Tipo | Descripción |
|---|---|---|
| `nodes` | `GraphEntityResponse[]` | Nodos del camino (2 a 7 nodos) |
| `relations` | `GraphRelationResponse[]` | Relaciones del camino (1 a 6 relaciones) |
| `length` | `int` | Número de saltos (1–6) |

---

## Respuestas de error comunes

Todos los errores siguen el mismo envelope:

```json
{
  "error": "CódigoDeError",
  "message": "Descripción legible",
  "request_id": "uuid-opcional"
}
```

Los errores de validación (422) incluyen además un campo `detail`:

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "detail": [
    {
      "loc": ["body", "document_ids", 0],
      "msg": "Value error, duplicate document ID: 1",
      "type": "value_error"
    }
  ]
}
```

| Código HTTP | Cuándo ocurre |
|---|---|
| 400 | Cabecera de servicio malformada o regla de negocio básica |
| 401 | Sin credenciales o token inválido |
| 403 | Credenciales válidas pero permisos insuficientes |
| 409 | Conflicto (p. ej. proceso ya en marcha) |
| 413 | Archivo demasiado grande |
| 415 | MIME type no soportado |
| 422 | Fallo de validación Pydantic |
| 429 | Límite de tasa superado |
| 500 | Error interno no controlado |
| 502 | Dependencia upstream (Ollama, servicio externo) devolvió error |
| 503 | Servicio o dependencia no disponible |
