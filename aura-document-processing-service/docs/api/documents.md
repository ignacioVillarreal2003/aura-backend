# Documentos: ingesta, procesamiento y recuperación

Este documento resume los **grupos de endpoints** relacionados con documentos. La
referencia campo a campo está en [`endpoints.md`](endpoints.md) y en **OpenAPI**
(`/api/openapi.json` o Swagger `/api/docs`). Base URL: `/api/v1`.

## Creación e ingesta

### Subir un documento
- **Ruta:** `POST /api/v1/create-document` · `multipart/form-data`.
- **Campos típicos:** `file` (parte multipart), `chat_id?`, `prefer_docling`, `enrich`, `graph_extract`, `name?`.
- **Comportamiento:** valida el archivo (tipo, tamaño, magic-number), guarda el binario en
  almacenamiento de objetos, persiste metadatos y **encola** la ingesta (extracción de
  texto → limpieza → fragmentación → embeddings → persistencia). El estado del documento
  evoluciona en base de datos (`uploaded` → `processed`/`failed`).

### Alta masiva
- **Ruta:** `POST /api/v1/bulk-create-document` · `multipart/form-data` con `files[]`.
- Cada archivo se procesa de forma independiente; la respuesta detalla el resultado por archivo.

### Post-procesado durante la ingesta
No expone endpoints propios en la creación: se dispara con dos banderas del formulario:

- `enrich` (default `false`): clasifica el documento (tipo/categoría/descripción) y
  **contextualiza** sus fragmentos (genera `contextualized_content` y su embedding).
- `graph_extract` (default `false`): encola la extracción del grafo de conocimiento.

Ambas corren **best-effort** tras persistir los fragmentos; un fallo en el post-procesado
no invalida la ingesta. También pueden reejecutarse después como jobs de mantenimiento
(ver más abajo).

## Edición y restauración

| Operación | Método y ruta |
|---|---|
| Actualizar título (manage) | `PATCH /api/v1/update-document/manage/document/{document_id}` |
| Restaurar documento borrado (manage) | `POST /api/v1/restore-document/manage/document/{document_id}` |

## Recuperación (consulta y descarga)

Prefijo **`/api/v1/document-query`**:

| Operación | Método y ruta |
|---|---|
| Detalle de un documento (manage) | `GET /manage/document/{document_id}` |
| Estado de procesamiento | `GET /document/{document_id}/status` |
| Estado de procesamiento (manage) | `GET /manage/document/{document_id}/status` |
| Listado paginado/filtrado (manage) | `GET /manage/documents` |
| Documentos de un chat | `GET /documents/chat/{chat_id}` |

Descarga binaria — prefijo **`/api/v1/document-download`**:

| Operación | Método y ruta |
|---|---|
| Descargar | `GET /document/{document_id}/download` |
| Descargar (manage) | `GET /manage/document/{document_id}/download` |

## Búsqueda por contenido

- **Ruta:** `POST /api/v1/document-search/by-content`.
- Similitud `vector` / `bm25` / `hybrid`, paginada. Contrato en [`endpoints.md`](endpoints.md).

## Contexto vía fragmentos (RAG)

Prefijo **`/api/v1/fragment-query`**: `POST /by-question` (consultas semánticas/BM25 con
reranking opcional) y `POST /by-documents` (fragmentos de una lista de documentos, con
submuestreo representativo por documento). Detalle en [`endpoints.md`](endpoints.md).

## Borrado

Prefijo **`/api/v1/delete-document`** — solo **borrado lógico** (soft delete):

| Operación | Método y ruta |
|---|---|
| Borrado lógico de un documento | `DELETE /soft/document/{document_id}` |
| Borrado lógico de documentos de un chat | `DELETE /soft/chat/{chat_id}` |
| Borrado lógico de un documento (manage) | `DELETE /manage/soft/document/{document_id}` |

Responden **204** sin cuerpo. La purga física del binario y de la huella en el grafo se
realiza de forma **asíncrona** tras el borrado lógico (vía cola de purga), no por un
endpoint HTTP dedicado.

## Mantenimiento (jobs asíncronos, manage)

Reejecutan pipelines sobre uno, varios o todos los documentos, con estado y parada:

| Pipeline | Prefijo |
|---|---|
| Re-embedding | `/api/v1/document-reembed/manage` |
| Reprocesamiento | `/api/v1/document-reprocess/manage` |
| Enriquecimiento | `/api/v1/document-enrich/manage` |
| Extracción de grafo | `/api/v1/graph/extraction/manage` |

Cada uno: `POST` (lanzar) → `202`, `GET /status`, `DELETE /stop`. Ver
[`endpoints.md`](endpoints.md) para el selector y los modelos de estado.

## Resumen

- **Ingesta:** `POST /create-document` y `POST /bulk-create-document`, con `enrich` y
  `graph_extract` (default `false`).
- **Edición:** `update-document`, `restore-document` (manage).
- **Retrieve:** `document-query`, `document-download`, `document-search`.
- **Fragmentos/RAG:** `fragment-query` (contrato en `endpoints.md` / OpenAPI).
- **Borrado:** `delete-document` (solo lógico; purga física asíncrona).
- **Mantenimiento:** `document-reembed`, `document-reprocess`, `document-enrich`, `graph/extraction` (jobs manage).
