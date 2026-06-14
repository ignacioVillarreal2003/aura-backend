Chunking jerárquico	hierarchical_chunking()	Crea chunks pequeños (256 chars) para recuperación y chunks padres grandes (1024 chars) para contexto



He analizado a fondo el pipeline RAG de aura-document-processing-service.
  Acá está el diagnóstico completo: primero qué ya tenés (que es mucho y muy
  bueno), y después lo que falta para que sea "perfecto", priorizado y
  fundamentado con prácticas actuales.

  Lo que YA tenés (base sólida, nivel producción)

  Tu RAG no es básico — ya implementa varias técnicas que la mayoría no tiene:

  - Retrieval híbrido: vectorial (pgvector, cosine <=>) + léxico BM25
  (ParadeDB @@@ / paradedb.score) — fragment_repository.py
  - Fusión RRF (Reciprocal Rank Fusion, k=60) entre múltiples listas
  semánticas y BM25 — fragment_query_service.py:53
  - Multi-query: acepta varias semantic_queries y bm25_queries por request
  - Reranking con cross-encoder (sentence-transformers, con min_score y
  fallback) — cross_encoder_reranker.py
  - Expansión de contexto adyacente (window de chunks vecinos) —
  get_adjacent_fragments
  - GraphRAG: Neo4j, extracción de entidades/relaciones, /graph/context con
  expansión de vecinos y provenance
  - Enrichment por fragmento (summary, entities, topics)
  - Chunking recursivo por tokens (tiktoken cl100k_base, 512/50) + opción de
  splitter semántico HF
  - Embedders flexibles (Ollama nomic/qwen3/mxbai, o HF e5/bge-m3) con manejo
  correcto de prefijos asimétricos e5
  - Resiliencia: circuit breaker, retries, threshold de similitud configurable

  Es una arquitectura muy por encima del promedio. Lo que sigue son los huecos
  reales hacia "perfecto".

  ---
  Lo que FALTA, por orden de impacto

  🔴 1. Contextual Retrieval (el hueco más grande y más rentable)

  Hoy embebés solo el texto crudo del chunk (document_ingestion_service.py:101
  → _embed_chunks(chunks)). El chunk pierde el contexto del documento: "El
  margen creció 3%" no sabe de qué empresa ni año.

  La técnica de Contextual Retrieval de Anthropic prepende a cada chunk un
  breve contexto generado por LLM (de qué trata, dentro de qué
  documento/sección) antes de embeber y de indexar en BM25. Reduce errores de
  retrieval hasta 49–67% combinado con reranking.

  Lo notable: vos ya tenés toda la infraestructura para esto. Tenés enrichment
  que genera summary por fragmento, y un LLM provider. Solo falta que el
  texto que se embebe/indexa sea contexto + summary + content en vez de solo
  content. Es el mayor ROI disponible.

  ▎ Fuentes: Anthropic Contextual Retrieval (DataCamp)
  ▎ (https://www.datacamp.com/tutorial/contextual-retrieval-anthropic), AWS
  ▎ Bedrock contextual retrieval (https://aws.amazon.com/blogs/machine-learnin
  ▎ g/contextual-retrieval-in-anthropic-using-amazon-bedrock-knowledge-bases/)

  🔴 2. Estrategia de chunking: pasar de recursivo fijo a
  estructural/semántico

  RecursiveCharacterTextSplitter por tokens (512/50) es robusto pero ciego a
  la estructura: parte tablas, listas y headers a la mitad. Ya usás Docling
  como reader — Docling produce estructura (headings, tablas, secciones) que
  estás descartando al pasar a texto plano.

  Mejoras actuales:
  - Chunking estructural respetando headers/tablas de Docling (HybridChunker
  de Docling existe para esto).
  - Late Chunking (Jina, 2024-25): embeber el documento largo primero y recién
  después partir, así cada embedding ya "vio" el contexto. Alternativa más
  barata que Contextual Retrieval (no requiere llamadas LLM por chunk), aunque
  algo menos preciso. Tu modelo bge-m3 soporta 8192 tokens — ideal para late
  chunking.
  - Adjuntar metadata al chunk (título de sección, página) — mejora retrieval
  y citas.

  ▎ Fuentes: Late Chunking (arXiv 2409.04701)
  ▎ (https://arxiv.org/pdf/2409.04701), Best Chunking Strategies 2026
  ▎ (Firecrawl) (https://www.firecrawl.dev/blog/best-chunking-strategies-rag),
  ▎ Reconstructing Context (arXiv 2504.19754)
  ▎ (https://arxiv.org/abs/2504.19754)

  🟠 3. No hay evaluación medible (no podés saber si "mejora")

  Este es el hueco metodológico crítico: no encontré ningún harness de
  evaluación de RAG. Sin esto, "mejorar el RAG" es a ciegas — cualquier cambio
  (chunk size, threshold, reranker) es opinión, no dato.

  Necesitás:
  - Un golden dataset (preguntas → chunks/respuestas correctas, versionado).
  - Métricas de retrieval: Recall@k, Precision@k, MRR, Context
  Precision/Recall.
  - Métricas de generación: Faithfulness (grounding, anti-alucinación), Answer
  Relevance, Answer Correctness.
  - Herramienta: RAGAS (reference-free, genera test sets sintéticos) o
  TruLens, corriendo en CI.

  Sin esto no podés afinar los muchos parámetros que ya tenés
  (similarity_threshold=0.65, bm25_rrf_k, recursive_split_size, top_n del
  reranker).

  ▎ Fuentes: Guía RAG Evaluation 2025 (Maxim)
  ▎ (https://www.getmaxim.ai/articles/complete-guide-to-rag-evaluation-metrics
  ▎ -methods-and-best-practices-for-2025/), RAGAS / Meilisearch
  ▎ (https://www.meilisearch.com/blog/rag-evaluation), Searching for Best
  ▎ Practices in RAG (arXiv 2407.01219) (https://arxiv.org/pdf/2407.01219)

  🟠 4. Transformación de query (query understanding)

  Soportás multi-query, pero la generación de esas queries vive en el
  llm-service y no vi señales de las técnicas más efectivas:
  - HyDE (Hypothetical Document Embeddings): generar una respuesta hipotética
  y embeberla — funciona muy bien cuando la pregunta es corta y el corpus
  técnico.
  - Query decomposition: partir preguntas multi-hop en sub-preguntas.
  - Query rewriting/expansion con sinónimos del dominio.
  - Routing: decidir si una query necesita vector, BM25, grafo o los tres (hoy
  parece que el cliente lo decide manualmente con los arrays de queries).

  🟡 5. Detalles del retrieval híbrido que dejan recall sobre la mesa

  - Pool de candidatos chico antes del rerank: el k de cada query es el
  max_fragments del request. La buena práctica es recuperar un pool amplio
  (ej. 50–100) y dejar que el cross-encoder elija el top-n. Si el k de entrada
  es ~5, el reranker tiene poco material que ordenar.
  - RRF vs. fusión ponderada: RRF puro ignora los scores. Para queries muy
  léxicas (códigos, nombres propios) conviene poder pesar BM25 sobre vector y
  viceversa.
  - similarity_threshold=0.65 fijo y alto: con cosine sobre modelos
  multilingües, 0.65 puede descartar buenos pasajes. Esto se valida con el
  harness de evaluación (punto 3), no a ojo.
  - MMR / diversificación: no hay control de redundancia. Hoy adjacent_chunks
  puede llenar el contexto de fragmentos casi idénticos. MMR (Maximal Marginal
  Relevance) equilibra relevancia vs. diversidad.

  🟡 6. GraphRAG: matching de entidades frágil

  graph_context_service.py matchea entidades por prefijo de nombre canónico +
  fulltext. Es exact/prefix-match: "IBM" no matchea "International Business
  Machines", ni hay tolerancia a typos. Mejora: resolución de entidades por
  embedding (vectorizar nombres de entidad) o alias/linking. También evaluá
  community summaries (estilo Microsoft GraphRAG) para preguntas globales tipo
  "¿de qué trata todo el corpus?".

  🟡 7. Embeddings: el default multilingüe es el más débil

  El default es paraphrase-multilingual-MiniLM-L12-v2 (384 dims). Para español
  en producción, BAAI/bge-m3 (1024d, multilingüe, soporta
  dense+sparse+ColBERT multi-vector y 8k contexto) o
  intfloat/multilingual-e5-large rinden bastante mejor. Ya los tenés en la
  lista de modelos permitidos — es cuestión de elegir bien el default y
  medirlo. Bonus: bge-m3 te da BM25/sparse "gratis" desde el mismo modelo.

  🟢 8. Otros refinamientos

  - Caching de embeddings de queries (las preguntas se repiten).
  - Citaciones/grounding explícito: devolver spans exactos usados para
  responder (mejora confianza y permite medir faithfulness).
  - Deduplicación a nivel de ingestión (chunks repetidos entre documentos
  inflan el contexto).
  - Feedback loop: ya tenés sistema de like/dislike en memoria — conectarlo
  como señal para reordenar/afinar retrieval cerraría el círculo.

  ---
  Resumen priorizado

  ┌───────────┬───────────────────────────────┬──────────┬────────────────┐
  │ Prioridad │            Mejora             │ Esfuerzo │    Impacto     │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 1         │ Harness de evaluación (RAGAS  │ Medio    │ Habilita todo  │
  │           │ + golden set)                 │          │ lo demás       │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 2         │ Contextual Retrieval          │ Medio    │ -50% errores   │
  │           │ (contexto pre-embedding)      │          │ retrieval      │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 3         │ Chunking estructural/late     │ Medio    │ +2-18%         │
  │           │ (aprovechar Docling/bge-m3)   │          │ precisión      │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 4         │ Pool amplio antes de rerank + │ Bajo     │ Recall directo │
  │           │  tuning de threshold          │          │                │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 5         │ Query transformation          │ Medio    │ Preguntas      │
  │           │ (HyDE/decomposition)          │          │ complejas      │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 6         │ Mejor default de embeddings   │ Bajo     │ Calidad base   │
  │           │ (bge-m3) + medirlo            │          │                │
  ├───────────┼───────────────────────────────┼──────────┼────────────────┤
  │ 7         │ Entity resolution en GraphRAG │ Alto     │ Casos          │
  │           │  / MMR                        │          │ específicos    │
  └───────────┴───────────────────────────────┴──────────┴────────────────┘

  El patrón clave: tenés casi todas las piezas de un RAG de élite, pero te
  falta (a) el contexto en los embeddings y (b) una forma de medir. Sin el
  punto 1 no podés afinar con confianza los muchos parámetros que ya
  expusiste; con los puntos 1+2+3 saltás de "muy bueno" a "estado del arte".

  ¿Querés que prepare un plan de implementación para alguno en concreto (ej.
  el harness de evaluación o Contextual Retrieval), o que profundice el
  análisis de la generación de queries en el llm-service, que es la parte que
  no llegué a ver?

  Sources: Anthropic Contextual Retrieval (DataCamp)
  (https://www.datacamp.com/tutorial/contextual-retrieval-anthropic) · AWS
  │ 3         │ Chunking estructural/late (aprovechar Docling/bge-m3) │ Medio    │ +2-18% precisión       │
  ├───────────┼───────────────────────────────────────────────────────┼──────────┼────────────────────────┤
  │ 4         │ Pool amplio antes de rerank + tuning de threshold     │ Bajo     │ Recall directo         │
  ├───────────┼───────────────────────────────────────────────────────┼──────────┼────────────────────────┤
  │ 5         │ Query transformation (HyDE/decomposition)             │ Medio    │ Preguntas complejas    │
  ├───────────┼───────────────────────────────────────────────────────┼──────────┼────────────────────────┤
  │ 6         │ Mejor default de embeddings (bge-m3) + medirlo        │ Bajo     │ Calidad base           │
  ├───────────┼───────────────────────────────────────────────────────┼──────────┼────────────────────────┤
  │ 7         │ Entity resolution en GraphRAG / MMR                   │ Alto     │ Casos específicos      │
  └───────────┴───────────────────────────────────────────────────────┴──────────┴────────────────────────┘

  El patrón clave: tenés casi todas las piezas de un RAG de élite, pero te falta (a) el contexto en los embeddings y (b) una forma de medir. Sin el punto 1 no podés afinar con confianza
  los muchos parámetros que ya expusiste; con los puntos 1+2+3 saltás de "muy bueno" a "estado del arte".

  ¿Querés que prepare un plan de implementación para alguno en concreto (ej. el harness de evaluación o Contextual Retrieval), o que profundice el análisis de la generación de queries
  en el llm-service, que es la parte que no llegué a ver?

  Sources: Anthropic Contextual Retrieval (DataCamp) (https://www.datacamp.com/tutorial/contextual-retrieval-anthropic) · AWS Bedrock Contextual Retrieval
  (https://aws.amazon.com/blogs/machine-learning/contextual-retrieval-in-anthropic-using-amazon-bedrock-knowledge-bases/) · Late Chunking (arXiv 2409.04701)
  (https://arxiv.org/pdf/2409.04701) · Reconstructing Context (arXiv 2504.19754) (https://arxiv.org/abs/2504.19754) · Best Chunking Strategies 2026 (Firecrawl)
  (https://www.firecrawl.dev/blog/best-chunking-strategies-rag) · RAG Evaluation Guide 2025 (Maxim)
  (https://www.getmaxim.ai/articles/complete-guide-to-rag-evaluation-metrics-methods-and-best-practices-for-2025/) · RAG Evaluation (Meilisearch/RAGAS)
  (https://www.meilisearch.com/blog/rag-evaluation) · Searching for Best Practices in RAG (arXiv 2407.01219) (https://arxiv.org/pdf/2407.01219)
