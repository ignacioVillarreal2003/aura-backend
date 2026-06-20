# Documentos: ingesta, procesamiento y recuperación

Este documento resume los **grupos de endpoints** relacionados con documentos. Los nombres de campos, modelos de respuesta y códigos exactos están en **OpenAPI** (`/api/openapi.json` o Swagger `/api/docs`).

## Creación e ingesta

### Subir un documento

- **Método y ruta:** `POST /api/create-document/`
- **Tipo:** `multipart/form-data`.
- **Campos de formulario típicos:** identificador de chat (`chat_id`), flag opcional de preferencia por pipeline (`prefer_docling`), y el archivo del documento como parte del multipart.
- **Comportamiento esperado:** el servicio persiste metadatos, guarda el binario en almacenamiento de objetos y encola u orquesta el procesamiento (extracción de texto, fragmentación, embeddings, etc.) según la configuración del entorno.

La ingesta suele ser el punto de entrada del **pipeline** asíncrono; el estado del documento evoluciona en base de datos mientras avanzan las etapas.

### Post-procesado en la creación

El post-procesado (clasificación del documento + enriquecimiento de fragmentos y extracción del grafo de conocimiento) ya no expone endpoints propios: se dispara **durante la ingesta** a partir de dos banderas del formulario de creación:

- `enrich` (bool, default `false`): clasifica el documento (tipo/categoría/descripción) y enriquece sus fragmentos (resumen, entidades, temas).
- `graph_extract` (bool, default `false`): encola la extracción del grafo de conocimiento.

Ambas se ejecutan de forma **best-effort** tras persistir los fragmentos; un fallo en el post-procesado no invalida la ingesta.

## Recuperación (consulta y descarga)

### Consulta de metadatos y listados

Prefijo **`/api/document-query`**:

| Operación (resumen) | Método y ruta |
|---------------------|---------------|
| Detalle de un documento | `GET /api/document-query/document/{document_id}` |
| Listado paginado/filtrado | `GET /api/document-query/documents` |
| Documentos asociados a un chat | `GET /api/document-query/documents/chat/{chat_id}` |

Los filtros de listado (nombre, descripción, categoría, tipo, rangos de fechas, paginación) se documentan como query parameters en OpenAPI.

### Descarga del archivo

- **Método y ruta:** `GET /api/document-download/document/{document_id}/download`
- **Respuesta:** cuerpo binario con cabeceras de contenido y disposición de descarga adecuadas al tipo MIME almacenado.

### Contexto vía fragmentos (solo referencia)

Bajo **`/api/fragment-query`** hay endpoints para obtener fragmentos de contexto (por pregunta o por conjunto de documentos), orientados a escenarios de RAG o recuperación semántica. **No** se detallan aquí los cuerpos ni límites; usar **Swagger/ReDoc** o el JSON de OpenAPI.

## Borrado

Prefijo **`/api/delete-document`**:

| Operación (resumen) | Método y ruta |
|---------------------|---------------|
| Borrado lógico de un documento | `DELETE /api/delete-document/soft/document/{document_id}` |
| Borrado lógico de documentos de un chat | `DELETE /api/delete-document/soft/chat/{chat_id}` |
| Borrado físico de un documento | `DELETE /api/delete-document/hard/document/{document_id}` |
| Borrado físico de documentos de un chat | `DELETE /api/delete-document/hard/chat/{chat_id}` |

Las respuestas suelen ser **204** sin cuerpo cuando la operación concluye correctamente; las reglas de autorización y efectos en almacenamiento o colas dependen de la implementación del servicio (ver OpenAPI y código de aplicación).

## Resumen

- **Ingesta:** `POST /api/create-document/` con banderas `enrich` y `graph_extract` (default `false`) que disparan el post-procesado durante la ingesta.
- **Retrieve:** `GET /api/document-query/...` y `GET /api/document-download/...`.
- **Fragmentos para contexto:** `/api/fragment-query/...` (contrato en OpenAPI).
- **Borrado:** `/api/delete-document/...` (soft/hard, por documento o por chat).
