


4. El control de acceso es "traer TODOS los IDs accesibles" por cada query, vía HTTP paginado, y luego filtrar/pasar esa
   lista gigante a SQL = ANY(...). Latencia en hot-path + pérdida silenciosa de recall al truncar en        
   max_pages.
5. No hay versionado de modelo de embedding por fragmento. La dimensión del vector se "hornea" en la columna ORM en
   import-time. Cambiar de modelo = re-embeber todo, sin camino seguro de reindexado y con riesgo de mezclar     
   espacios vectoriales.
6. Metadata de chunk pobrísima: solo fragment_index. Sin página, sección, jerarquía, offsets ni parent. Imposible citar
   página o reconstruir contexto estructural; split_size/split_overlap nunca se persisten.



  ---

2. Hallazgos Críticos

C1 — Búsqueda vectorial sin índice ANN (KNN exacto)

orm/fragment.py:32 declara vector = Column(VECTOR(dim=...)) sin índice. El grep confirma: no existe ningún CREATE
INDEX ... USING hnsw/ivfflat en todo el repo (solo índices Neo4j). En fragment_repository.py:136-160 y :253-275
la query hace ORDER BY 1 - (vector <=> :q) DESC LIMIT k con un WHERE ... >= threshold y document_id = ANY(:doc_ids).

- Sin índice ANN → Postgres calcula coseno contra cada fila no borrada. O(N) por query.
- Con 5M fragmentos esto son segundos por búsqueda y colapsa el pool de conexiones bajo concurrencia.
- El filtro >= threshold + = ANY(doc_ids) además degrada cualquier HNSW futuro (filtered search) si no se planifica con
  iterative scan o partial indexes.

Impacto: el RAG no escala más allá de ~decenas de miles de fragmentos. Es el bug arquitectónico más grave.

C3 — Idempotencia muerta → documentos y fragmentos duplicados

api/dependencies/idempotency.py solo guarda la cabecera en request.state.idempotency_key y no está cableada en ningún
controlador (grep confirma uso nulo). create_document no es idempotente: reintentos de cliente/red crean    
documentos duplicados (con su re-ingesta, re-embedding y re-extracción de grafo = coste multiplicado).

Además no hay UniqueConstraint(document_id, fragment_index) (grep: cero constraints en el ORM). Si el lock de ingesta (
document_ingestion_lock_ttl_seconds) expira mientras la ingesta sigue corriendo y RabbitMQ reentrega, se   
ejecuta una segunda ingesta concurrente → fragmentos duplicados sin protección de BD.



  ---

3. Problemas de Arquitectura

- Outbox no transaccional real. En create_document_service.py:164 se hace commit() del documento y después se publica
  vía outbox_lite. El evento no se escribe en la misma transacción que la fila. Mitigado por
  get_stale_uploaded_documents + OutboxLiteWorker, pero sigue siendo "best effort" sobre Redis: si Redis se pierde, los
  eventos en vuelo se pierden (solo se recuperan los uploaded colgados, no los eventos de enrichment/graph que
  fallan silenciosamente en _publish_* con logger.warning).

- Acoplamiento del pipeline a un único hilo de proceso. Ingesta lee→limpia→split→embed→persiste secuencialmente por
  documento; correcto funcionalmente, pero no hay backpressure por tamaño ni paralelización por documento       
  grande.

  ---

4. Problemas de Retrieval

- Acceso por "lista completa de IDs accesibles" (C4/C1). fetch_all_accessible_document_ids (
  document_collection_catalog_client.py) pagina HTTP en el hot-path de cada búsqueda y trunca en max_pages (línea 96):
  un usuario con   
  más documentos accesibles que max_pages*page_size recibe un set truncado arbitrariamente → recall silenciosamente
  incompleto. Y esa lista (potencialmente miles de IDs) se inyecta en = ANY(:doc_ids) en cada query SQL.
- Fail-closed que parece fail-open de calidad: ante cualquier error del catálogo, devuelve frozenset() → búsqueda
  devuelve vacío. Bueno para seguridad, malo para alucinaciones: el LLM aguas abajo recibe cero contexto sin señal
  de error y responde igual. No se distingue "sin resultados" de "fallo de autorización".

- RRF puro por rango (_reciprocal_rank_fusion, :57). Razonable, pero no normaliza scores ni permite ponderar BM25 vs
  vector (importante para queries léxicas: códigos, nombres propios, números de norma). Si solo hay 1 lista    
  (una semantic query, sin BM25) no hay fusión.
- 
- 

  ---


  ---

6. Problemas de Embeddings

- Dimensión horneada en import-time (orm/fragment.py:12-15, @lru_cache sobre EmbedderSettings().vector_dimension). El
  modelo se fija a nivel de columna. No hay columna embedding_model/embedding_version/dim por fragmento.
- Cambiar de modelo es un acantilado: dimensiones distintas → la columna VECTOR(dim=N) no admite otra dim; mismo dim
  pero distinto modelo → se mezclan espacios vectoriales y el coseno query-vs-fragment queda sin sentido, sin  
  ninguna detección. No existe pipeline de reindexado/backfill ni doble escritura.
- Query y documentos deben usar el mismo modelo/instrucciones. Para e5 se auto-aplican prefijos query:/passage: (
  embedder_settings.py:133-137), pero como no se guarda qué modelo generó cada vector, una migración parcial       
  produce resultados incorrectos silenciosos.
- Reembedding ciego en reingesta: si un documento se reprocesa, se generan fragmentos nuevos pero no hay deduplicación
  contra los viejos (ver C3).

  ---

7. Problemas del Grafo

- Resolución de entidades por igualdad exacta de nombre canónico (lowercased/espacios colapsados, _canonicalize_name).
  Sin fuzzy/alias-embedding/coref. "EE.UU." vs "USA" vs "Estados Unidos" → 3 nodos distintos. Fragmentación  
  masiva del grafo y recall de grafo pobre.
- source_document_ids como array creciente en cada nodo/relación. Los filtros de acceso hacen any(d IN coalesce(
  e.source_document_ids,[]) WHERE d IN $accessible_ids) en cada nodo evaluado (entity repo, relation repo, path     
  repo). Esto no usa índice: es un scan de array por nodo × tamaño de accessible_ids. Con entidades populares (un país,
  una ley) el array tendrá miles de IDs → coste O(n·m) por consulta.
- Problema de supernodos. Entidades comunes acumularán grado enorme de relaciones REL. Las traversales de
  graph_path/graph_context sobre supernodos serán lentísimas y sin límite de fan-out documentado.
- Borrado del grafo inexistente (C2): además de la fuga, no hay decremento de source_document_ids ni limpieza de
  entidades que se quedan sin ningún documento fuente accesible → quedan "fantasmas" recuperables.
- Extracción cara y frágil: una llamada LLM por fragmento (_process_single_fragment). Con sliding window (
  extraction_sliding_window_chars > 0) el procesamiento es totalmente secuencial (anula el Semaphore), inviable
  para      
  documentos grandes. Trunca fragmentos por encima de extraction_max_fragments_per_document → pérdida de información de
  grafo silenciosa para documentos largos.
- Progreso del job en Redis (memoria) sin durabilidad garantizada; si Redis cae, se pierde el estado del job.

  ---

8. Problemas de Consistencia

- Estados parciales entre los 3 stores. Un documento processed en Postgres puede no tener grafo (publicación de evento
  falló con solo warning, document_ingestion_service.py:398-423). No hay reconciliación de
  graph_status=pending colgados (solo de uploaded).
- Fragmentos duplicados por lock expirado (C3) + ausencia de unique constraint.
- Enrichment/graph events best-effort: si _publish_document_enrichment_event falla, el documento queda enriquecido a
  medias y nadie reintenta.
- Reranking + adjacent + dedup: el orden es rerank → añadir adyacentes → dedup (fragment_query_service.py:200-231).
  Correcto, pero los adyacentes entran después del corte top_n, inflando el contexto por encima de lo pedido    
  (impacto en coste de tokens aguas abajo).

  ---

9. Problemas de Escalabilidad

┌──────────────────────────────────────┬──────────────────────────────────────────────────────┐
│ Punto │ Límite │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Vector search │ O(N) sin ANN (C1) — colapsa en ~10⁴–10⁵ fragmentos │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Lista de acceso │ HTTP paginado por query + truncación (recall loss)   │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ = ANY(doc_ids)                       │ miles de IDs por query, mata el plan │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Neo4j access filter │ scan de array por nodo, supernodos │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Grafo extracción │ 1 LLM/fragmento, secuencial con sliding window │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ get_documents admin │ ilike '%term%' no sargable = seq scan total │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Soft-delete sin purga │ bloat ilimitado en 3 stores │
├──────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ get_documents_by_chat_id sin paginar │ cap MAX_DOCUMENTS_IN_LIST pero carga todo en memoria │
└──────────────────────────────────────┴──────────────────────────────────────────────────────┘

  ---

10. Problemas de Seguridad

- get_documents (listado admin, document_query_service.py:97-191) NO aplica filtro de acceso por documento. Devuelve
  documentos de todos los tenants que matcheen filtros; solo protegido por un permiso de controlador
  (document_query_controller.py:67). Si ese permiso es grueso, es una exposición cross-tenant / cross-clasificación.
- Sin aislamiento físico multi-tenant (C4). Todo en tablas/grafo compartidos.
- Autorización delegada y "fail-open de disponibilidad": ante caída del catálogo, retrieval devuelve vacío (ok para
  fuga) pero _require_document_access (query service) cae a chat membership — rutas de decisión múltiples y     
  difíciles de auditar.
- Token de usuario propagado a workers (base_consumer.py:125-149 + auth_token en el command). El bearer del usuario
  viaja dentro del mensaje en la cola y se persiste en el outbox de Redis (redis_outbox_lite.py guarda body con
  el token). Credencial sensible en reposo en Redis/RabbitMQ. Riesgo de robo de token y replay durante el TTL.
- fallback_bearer_token en el catálogo client (:128) — credencial estática de servicio; si se filtra, acceso amplio.
- Validación de upload sólida (magic numbers, path traversal, null bytes, tamaño) — esto sí está bien hecho.

  ---

11. Problemas de Performance (Hot Paths)

1. Vector search full-scan (C1).
2. Catálogo de acceso: N round-trips HTTP por búsqueda + JSON parsing.
3. Cross-encoder reranker en run_in_executor(None) (cross_encoder_reranker.py:109) → usa el ThreadPool por defecto,
   compite con asyncio.to_thread de embeddings y limpieza; en CPU es el segundo cuello tras el vector scan. Sin  
   batching adaptativo ni límite de candidatos de entrada (rerankea todo el pool fusionado).
4. Embeddings en CPU por defecto (huggingface_device="cpu", ollama default); asyncio.gather de varias queries semánticas
   serializa en el modelo.
5. Transferencia inútil de vectores en cada hit (sección 4).

  ---

12. Bugs Potenciales (concretos)

- B1 — Fragmentos duplicados por lock TTL expirado sin unique constraint (C3).
- B2 — Documentos duplicados por falta de idempotencia (C3).
- B3 — split_size/split_overlap siempre NULL (sección 5) → trazabilidad rota.
- B4 — Pérdida silenciosa de recall por truncación en max_pages del catálogo (sección 4).
- B5 — Mezcla de espacios vectoriales si se cambia el modelo sin reindexar, sin detección (sección 6).
- B6 — Documentos processed sin grafo/enrichment por publicación best-effort, sin reconciliación (sección 8).
- B7 — Grafo sigue exponiendo hechos de documentos borrados (C2) — bug de confidencialidad.
- B8 — Truncación de fragmentos en extracción de grafo → grafo incompleto en docs largos.
- B9 — get_documents admin sin filtro de tenant (sección 10).

  ---

13. Refactors Recomendados

Quick Wins (bajo esfuerzo / alto impacto)

- Crear índice HNSW (vector_cosine_ops) sobre fragment.vector + adoptar Alembic (un primer migration con índices y
  constraints). Es el cambio de mayor ROI del sistema.
- Añadir UniqueConstraint(document_id, fragment_index) + ON CONFLICT DO NOTHING en ingesta.
- Dejar de seleccionar vector en queries de retrieval (proyectar solo columnas usadas).
- Persistir split_size/split_overlap/embedding_model/dim por fragmento.
- Distinguir "sin resultados" de "fallo de autorización" (devolver error explícito al fallar el catálogo) para mitigar
  alucinaciones.
- Mover el auth_token fuera del payload del mensaje (usar un service token de scope mínimo + user_id, o credenciales por
  intercambio firmado).

Medium Refactors

- Cachear el set de IDs accesibles (Redis, TTL corto) por usuario y/o empujar el filtro de autorización al store (vista
  materializada / tabla de membership local) en vez de HTTP por query.
- Reranker: limitar candidatos de entrada, batch dedicado en executor propio, mover a GPU/servicio.
- Splitting estructural (heading/section-aware) aprovechando Docling; enriquecer metadata de chunk (
  página/sección/offset).
- Propagación de borrado a Neo4j (DETACH DELETE por documento o decremento de source_document_ids) y a MinIO + purga
  física de vectores (job de hard-delete diferido).
- Reconciliación de enrichment_status/graph_status colgados.

Major Refactors

- Aislamiento multi-tenant: tenant_id en todas las tablas + RLS en Postgres + partición/etiqueta por tenant en Neo4j.
- Versionado de modelo de embedding con doble escritura y reindexado en caliente (blue/green de índice).
- Resolución de entidades (entity resolution) con embeddings/aliases/fuzzy + control de supernodos.
- Outbox transaccional real (tabla outbox en la misma transacción que el documento), no best-effort sobre Redis.

  ---

14. Plan de Mejoras Priorizado

┌───────────┬─────────────────────────────────────────────────────────────────┬───────────────────────────────────┬────────────┬───────────────────────────────────────────────────┐
│ Prioridad │ Hallazgo │ Impacto │ Esfuerzo │ Recomendación │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P0 │ C1 — Sin índice ANN │ Crítico (retrieval no escala)     │ Medio │ HNSW + Alembic │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P0 │ C2 — Borrado no propaga (grafo/MinIO/vector)                    │ Crítico (fuga + confidencialidad) │ Medio │
Hard-delete diferido en 3 stores │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P0 │ C4/B9 — Multi-tenant sin aislamiento + listado admin sin filtro │ Crítico (fuga cross-tenant)       │ Alto │
tenant_id + RLS; filtrar get_documents │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P1 │ C3/B1/B2 — Idempotencia + unique constraint │ Alto (duplicados, coste)          │ Bajo │ Idempotency-Key real +
UniqueConstraint │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P1 │ Token de usuario en cola/Redis │ Alto (seguridad)                  │ Medio │ Service token de scope mínimo │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P1 │ B4 — Truncación de acceso → recall │ Alto (calidad/legal)              │ Medio │ Cache/empuje de filtro al store
│
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P1 │ A2 — Sin migraciones │ Alto (operación)                  │ Medio │ Adoptar Alembic │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P2 │ B5 — Versionado de embeddings │ Alto (correctitud futura)         │ Alto │ Columna modelo + reindexado │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P2 │ Chunking estructural + metadata (página/sección)                │ Alto (calidad RAG/citas)          │ Medio │
Section-aware splitting │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P2 │ Entity resolution + supernodos │ Medio-Alto (calidad grafo)        │ Alto │ Dedup por embeddings/alias │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P3 │ Reranker/embeddings en CPU, híbrido secuencial │ Medio (latencia)                  │ Medio │ Paralelizar +
GPU/servicio │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P3 │ Reconciliación enrichment/graph │ Medio (consistencia)              │ Bajo │ Sweeper de estados pending │
├───────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────┼────────────┼───────────────────────────────────────────────────┤
│ P3 │ Observabilidad de negocio + tracing │ Medio │ Bajo-Medio │ Métricas chunk/embed/retrieve/rerank/grafo + OTel │
└───────────┴─────────────────────────────────────────────────────────────────┴───────────────────────────────────┴────────────┴───────────────────────────────────────────────────┘

  ---

15. Observabilidad (evaluación)

- Logging: excelente cobertura estructurada con extra={} y niveles correctos. Bien.
- Métricas: solo prometheus_fastapi_instrumentator (HTTP genérico). Faltan métricas de negocio: latencia/throughput de
  chunking, embeddings, vector/BM25/híbrido, rerank, extracción de grafo; tamaños de pool de candidatos; tasa
  de fallback BM25; recall de acceso truncado.
- Tracing: no hay OpenTelemetry ni correlation ID propagado entre HTTP → cola → workers (el message_id ayuda pero no es
  un trace). Imposible seguir un documento end-to-end.

  ---

16. Score Final (1–10)

┌─────────────────────────────┬───────┬────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Dimensión │ Score │ Justificación │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Arquitectura │ 7 │ Hexagonal limpia, DI, outbox+reconciliación; penaliza falta de migraciones y BD/grafo compartidos │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Retrieval │ 4 │ Híbrido + RRF + rerank presentes, pero sin ANN, acceso truncable y secuencial │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Calidad RAG │ 4 │ Chunking ciego a estructura, metadata pobre, fail-closed que alimenta alucinaciones │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Escalabilidad │ 2 │ Full-scan vectorial, arrays de acceso en grafo, listas ANY gigantes │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Performance │ 4 │ Hot-paths en CPU, vectores transferidos sin uso, HTTP por query │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Seguridad │ 4 │ Buena validación de upload, pero sin aislamiento multi-tenant, token en cola, listado admin sin filtro
│
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Observabilidad │ 5 │ Logs muy buenos; sin métricas de negocio ni tracing │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Mantenibilidad │ 8 │ Interfaces/factories hacen trivial añadir readers/embedders/splitters/rerankers │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Calidad de Código │ 8 │ Consistente, tipado, manejo de errores cuidado │
├─────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Preparación para Producción │ 3 │ A la escala declarada y por C1–C4, no está listo │
└─────────────────────────────┴───────┴────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Global ponderado: ~4.5 / 10 — base de código de buena ingeniería, no apta aún para la escala y el perfil declarados.

  ---

17. Riesgos para una Implementación Militar / Institucional

- Confidencialidad / Desclasificación imposible: el borrado no purga MinIO, vectores ni grafo (C2). Un documento
  clasificado "eliminado" sigue recuperable vía grafo y su binario persiste. No hay "derecho al olvido" ni purga   
  verificable.
- Sin control de acceso por rangos/clasificación: la autorización es binaria (accesible o no) vía servicio externo; no
  hay niveles de clasificación, compartimentación (need-to-know), ni etiquetas de sensibilidad en
  fragmentos/entidades. Un usuario con acceso al documento ve todo su contenido y todo el subgrafo derivado.
- Aislamiento multi-tenant inexistente a nivel de datos (C4): todos los tenants/unidades comparten tabla y grafo. Un
  fallo lógico = fuga total. Falta RLS/partición.
- Trazabilidad/auditoría insuficiente: hay created_by/updated_by/deleted_by, pero no hay log de auditoría inmutable de
  accesos de lectura/recuperación (quién consultó qué fragmento clasificado y cuándo). Sin tracing end-to-end
  no se puede reconstruir una cadena de custodia.
- Credenciales en reposo: bearer del usuario almacenado en RabbitMQ y Redis (outbox). En entorno sensible, tokens en
  colas/cachés son un objetivo de exfiltración.
- Integridad de recuperación: la truncación silenciosa del set accesible (B4) y el fail-closed sin señal (sección 4)
  pueden ocultar información relevante sin que el operador lo sepa — inaceptable cuando una omisión tiene      
  consecuencias operativas.
- Pérdida de información en grafo de docs largos (truncación de fragmentos, B8): un documento doctrinal extenso queda
  parcialmente representado, sin aviso.

Recomendación mínima para ese perfil antes de cualquier despliegue: RLS + tenant_id + columna de clasificación con
filtrado obligatorio en TODO retrieval; purga física verificable en los 3 stores; auditoría inmutable de       
lecturas; eliminación del token de usuario de colas/cachés; y resolver C1 para que el sistema sea siquiera utilizable a
escala.
