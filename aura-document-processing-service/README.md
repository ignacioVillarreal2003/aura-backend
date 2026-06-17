

  ---
Hallazgos Críticos






Problemas de Arquitectura

- accessible_doc_ids materializa TODOS los ids accesibles (fetch_all_accessible_document_ids) y los pasa como ANY(:
  array). Un usuario con acceso a 500k docs → array de 500k
  enteros por query. Esto no escala; debería ser un join/RLS del lado DB.



  ---
Problemas de Retrieval

- 
- Post‑filtro de permisos después de fusionar/rerankear (:236): se recuperan k por query, se fusiona, y luego se
  descartan los no accesibles → se puede devolver menos de k
  resultados (o cero) aunque existan fragmentos accesibles relevantes más abajo. El filtro de permisos debería ir dentro
  del SQL siempre (ya se pasa doc_ids, pero el post‑filtro
  indica desconfianza del propio filtro).
- Re‑ranking solo sobre content (:246), sin título/heading/section_path. El cross‑encoder corre sobre todo el pool
  fusionado (latencia O(candidatos)); no hay cap defensivo del
  pool antes del reranker.
- adjacent_chunks (:253‑263) añade vecinos después del rerank → los vecinos no pasan por scoring y diluyen el top‑k
  rerankeado.

  ---
Problemas de Chunking

- Sí hay provenance estructural (fragment tiene page_number, section_path, heading, char_start/end, bbox) — fortaleza
  real para citaciones.
- Pero el fallback clásico produce fragmentos sin metadata estructural (NULL), y no hay señal en la respuesta de qué
  fragmentos son "ricos" vs "planos".
- _build_fragments asume zip(chunks, embeddings, strict=True) (:363) — correcto, pero si un chunk queda vacío tras
  limpieza se filtra antes (:232), lo que puede desalinear
  fragment_index respecto del documento fuente (los índices son posicionales sobre la lista filtrada, no sobre el
  documento original).

  ---
Problemas de Embeddings

- Se embeben todos los chunks de un documento en una sola llamada aembed_documents(chunks) (
  document_ingestion_service.py:318) sin cap de cantidad a este nivel. Un documento de
  50k chunks → batch gigante en memoria + riesgo de timeout/OOM. Un único fallo aborta todo el documento (sin reintento
  parcial por lote).
- Sin versión de modelo por fragmento (ver C‑2). No se puede responder "¿qué fragmentos hay que re‑embeber?".
- Soporte de embeddings asimétricos existe (huggingface_query_instruction, aembed_query) — bien — pero por defecto
  vacío (embedder_settings.py:70), así que con HF queda simétrico
  salvo configuración explícita.

  ---
Problemas del Grafo

- Bien resuelto el borrado de entidades compartidas: delete_document_entities quita el document_id de
  source_document_ids y solo borra entidades huérfanas
  (graph_entity_repository.py:218‑226). No hay sobre‑borrado. Fortaleza.
- Escalabilidad de extracción: la extracción usa LLM por documento con lock Redis; con millones de documentos el costo
  LLM y la concurrencia (extraction_concurrency) son el
  límite. Falta backpressure visible entre ingesta y extracción más allá de la cola.
- Deduplicación de entidades por canonical_name — riesgo de colisión (entidades homónimas distintas) o fragmentación (
  misma entidad, nombre distinto) sin entity resolution
  robusto. Riesgo de calidad de grafo a escala.

  ---
Problemas de Consistencia

- Saga creación↔ingesta: la creación commitea el documento y publica vía outbox (bien). Pero si la ingesta falla
  definitivamente, el documento queda failed y el objeto sigue en
  MinIO; no veo reconciliación que lo purgue → objetos huérfanos en storage para ingestas fallidas (la purga solo se
  dispara en delete).
- get_stale_uploaded_documents reconcilia uploaded viejos (bien), pero no hay equivalente para failed ni para fragmentos
  huérfanos.
- Mezcla de modelos (C‑2) puede dejar la tabla en estado donde unas queries fallan y otras no, según qué docs toquen.

  ---
Problemas de Escalabilidad

┌───────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Escala │ Comportamiento esperado │
├───────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 100k docs │ Retrieval ya degradado (full scan vectorial); aceptable solo con pocas QPS. │
├───────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1M docs │ Búsqueda semántica en segundos; Postgres CPU‑bound; ANY(:doc_ids) enorme para usuarios con mucho acceso. │
├───────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10M docs │ Inoperable sin ANN index, partición y hard‑delete. │
└───────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Límites arquitectónicos: (1) sin ANN, (2) sin sharding/partición de fragment, (3) autorización por arrays gigantes, (4)
extracción de grafo LLM‑bound, (5) bloat por soft‑delete
perpetuo.

  ---
Problemas de Seguridad

- C‑5 (multi‑tenant en app‑layer, sin RLS) es el principal.
- Dependencia total de servicios externos para autorización en cada query (fail‑open si el catálogo devuelve de más).
- [FIX en sesión] CORS permisivo (A‑2) y endurecimiento de producción/credenciales (A‑3) ya corregidos.
- BM25 sanitiza input (fragment_repository.py:25‑33) y el vector se serializa a string interpolado (:132) —
  interpolación de string en SQL para el vector; aunque los valores son
  floats validados, es un patrón frágil (preferir binding nativo de pgvector).
- Sin cifrado a nivel de campo ni clasificación documental (ver sección final).

  ---
Problemas de Performance

- Hot path retrieval: full scan vectorial (C‑1) + post‑filtro en memoria + reranker sobre todo el pool.
- Distancia coseno calculada 3 veces por fila en la query semántica (SELECT, WHERE, ORDER BY) — :157,160,162. Sin
  índice, se paga el cómputo completo.
- N+1 potencial en _build_fragment_responses y en la resolución de documentos (revisar; usa get_documents_by_ids por
  lote, lo cual es correcto).
- Embedding de query es sincrónico bloqueante envuelto en to_thread para HF (huggingface_embedder.py:131) — ok, pero
  añade latencia por query.

  ---
Bugs Potenciales

1. Desalineación de fragment_index tras filtrar chunks vacíos (document_ingestion_service.py:232,363).
2. accessible_doc_ids vacío cuando el catálogo falla → la query semántica con ANY([]) o sin cláusula puede devolver de
   más o de menos según rama; el post‑filtro lo salva, pero
   confirma que el SQL no es la barrera real.
3. Mezcla de dimensiones de vector → error en runtime en <=> (C‑2).
4. Objetos MinIO huérfanos en ingestas failed (sin purga).
5. BM25 min_score=0 inunda el RRF con ruido.
6. Reranker top_n fallback or len(
   fragments) — [introducido en M‑3, correcto por el validador, pero si algún día se permite max_fragments=0 cambia semántica].

  ---
Refactors Recomendados

Quick Wins (bajo esfuerzo / alto impacto)

- Crear índice HNSW sobre fragment.vector (requiere fijar dimensión primero). El mayor ROI del repo.
- Fijar dimensión: vector VECTOR(768) (o la del modelo activo) en el DDL.
- Workflow de CI para este servicio (copiar aura-chat-service.yml): ruff + mypy + pytest + build imagen + gate de
  cobertura. (Confirmado: existe el patrón para los hermanos,
  falta aquí.)
- min_score BM25 > 0 por defecto y cap del pool antes del reranker.
- Filtrar permisos siempre en SQL y eliminar dependencia del post‑filtro como barrera.

Medium Refactors

- Hard‑delete / retención de fragmentos soft‑deleted (job batch + partición por fecha).
- RRF ponderado + normalización de scores entre modalidades; exponer pesos configurables.
- Columna embedding_model/dim por fragmento + tabla de migración de embeddings.
- Embedding por lotes (respetar max_batch_size) con reintento parcial por lote.
- Tests de servicio + testcontainers (CreateDocumentService compensaciones, OutboxLiteWorker, consumers) — el objetivo
  de M‑4.

Major Refactors

- RLS / columna tenant en Postgres y Neo4j; mover autorización al data layer.
- Re‑ingest/reindex pipeline (update documento, migración de modelo).
- Sharding/partición de fragment y posible externalización del vector store (o pgvector particionado) para 10M+.
- Entity resolution robusto en el grafo.

  ---
Plan de Mejoras Priorizado

┌───────────┬──────────────────────────────────┬───────────────────────┬──────────┬──────────────────────────────────────┐
│ Prioridad │ Hallazgo │ Impacto │ Esfuerzo │ Recomendación │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P0 │ C‑1 Sin índice ANN │ Crítico (perf/escala) │ M │ Fijar dim + HNSW (vector_cosine_ops) │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P0 │ C‑2 Vector sin dimensión │ Crítico (corrupción)  │ S │ VECTOR(n) + columna modelo │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P0 │ C‑5 Multi‑tenant app‑layer │ Crítico (seguridad)   │ L │ RLS + columna tenant │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P1 │ C‑3 Sin hard‑delete │ Alto (bloat)          │ M │ Job retención + partición │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P1 │ C‑4 Sin reindex/update │ Alto (operabilidad)   │ L │ Pipeline re‑embed/update │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P1 │ Sin CI │ Alto (regresiones)    │ S │ Workflow ruff+mypy+pytest+build │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P1 │ RRF sin pesos + BM25 min_score=0 │ Alto (calidad)        │ S │ Fusión ponderada + umbral BM25 │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P2 │ Embedding sin batching/cap │ Medio (OOM)           │ M │ Lotes + reintento parcial │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P2 │ Objetos MinIO huérfanos (failed) │ Medio (storage)       │ S │ Reconciliador de failed │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P2 │ Post‑filtro de permisos │ Medio (recall/seg)    │ S │ Filtro en SQL │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P3 │ Tests servicio/integración │ Medio (calidad)       │ L │ testcontainers (M‑4)                 │
├───────────┼──────────────────────────────────┼───────────────────────┼──────────┼──────────────────────────────────────┤
│ P3 │ Entity resolution grafo │ Medio (calidad KG)    │ L │ Dedup/canonicalización │
└───────────┴──────────────────────────────────┴───────────────────────┴──────────┴──────────────────────────────────────┘

  ---
Score Final (1‑10)

┌─────────────────────────────┬───────┬───────────────────────────────────────────────────────────────────────────────────┐
│ Dimensión │ Score │ Nota │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Arquitectura │ 6 │ Hexagonal limpia, outbox/saga; lastrada por autorización en hot path y ORM legacy │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Retrieval │ 3 │ Sin ANN, RRF rank‑only, umbrales asimétricos │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Calidad RAG │ 5 │ Buena provenance/chunking estructural; fusión y reranking flojos │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Escalabilidad │ 2 │ Full scan vectorial + bloat + arrays de permisos │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Performance │ 3 │ Hot path dominado por seq scan exacto │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Seguridad │ 4 │ Multi‑tenant solo en app; sin RLS; mejoras A‑2/A‑3 ya aplicadas │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Observabilidad │ 5 │ Logs estructurados + request_id; faltan métricas de dominio y tracing │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Mantenibilidad │ 6 │ Factories/interfaces, tipado mejorado (M‑3); ORM legacy pendiente │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Calidad de código │ 6 │ Consistente, defensivo; métodos largos en parte refactorizados (M‑2)              │
├─────────────────────────────┼───────┼───────────────────────────────────────────────────────────────────────────────────┤
│ Preparación para producción │ 3 │ No apto a escala sin P0/P1 │
└─────────────────────────────┴───────┴───────────────────────────────────────────────────────────────────────────────────┘

  ---
Riesgos para una Implementación Militar / Institucional

1. Sin control de acceso por rangos/clasificación. No hay columna de clearance level ni classification (
   CONFIDENTIAL/SECRET/…) en document/fragment. La autorización es binaria
   (accesible o no) y delegada a servicios externos. No se puede imponer need‑to‑know por rango.
2. Aislamiento multi‑tenant sin garantía de DB (C‑5). Cualquier bug en el catálogo o en el filtro de aplicación expone
   documentos cruzados. En entorno clasificado esto es una
   brecha de confidencialidad. Exige RLS y, idealmente, bases/segmentos físicos por nivel.
3. Trazabilidad/auditoría insuficiente. Hay created_by/updated_by/deleted_by y logs con request_id, pero no hay un audit
   log inmutable de accesos de lectura/recuperación (quién
   recuperó qué fragmento clasificado y cuándo). Imprescindible para auditoría institucional.
4. Recuperación segura comprometida por el post‑filtro. Que los permisos se apliquen parcialmente en memoria (:236) tras
   traer datos de la DB significa que datos potencialmente
   no autorizados ya salieron del store hacia el proceso antes de filtrarse. Debe filtrarse en origen, sin excepción.
5. Borrado no garantizado (derecho al olvido / sanitización). Soft‑delete perpetuo en Postgres (C‑3): un documento "
   eliminado" sigue físicamente presente y es escaneado en cada
   query. Para sanitización clasificada se requiere hard delete verificable y purga de respaldos/índices.
6. Sin cifrado a nivel de campo ni gestión de claves visible para contenido/embeddings en reposo (más allá de lo que
   provea la infra).
7. Mezcla de modelos/dimensiones (C‑2) puede degradar silenciosamente la recuperación de inteligencia crítica sin
   alarma.

Conclusión institucional: en su estado actual no es apto para datos clasificados. Requiere, como mínimo: RLS +
clasificación por rango, filtrado de permisos 100% en el data
layer, audit log inmutable de recuperaciones, y hard‑delete verificable.
