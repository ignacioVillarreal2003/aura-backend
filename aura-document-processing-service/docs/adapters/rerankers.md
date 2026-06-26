# Rerankers

Re-ordenan los fragments recuperados con un modelo cross-encoder (más preciso que la similitud
vectorial) antes de devolverlos. Se selecciona por `RERANKER_*` vía `RerankerFactory`.

## CrossEncoderReranker (`cross_encoder`)

Usa un cross-encoder de Sentence Transformers, default **`BAAI/bge-reranker-v2-m3`** (familia bge-m3,
multilingüe). El modelo se carga **una sola vez** (singleton) y se **warmea al startup** para que la
primera query no pague la carga (~2GB). La inferencia se **serializa** (lock) para no contender la GPU.

| Variable | Default | Descripción |
| --- | --- | --- |
| `RERANKER_ACTIVE_TYPE` | `cross_encoder` | Tipo activo. |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-v2-m3` | Modelo cross-encoder. |
| `RERANKER_DEVICE` | `cuda` (env GPU) | `cpu` \| `cuda` \| auto (None). |
| `RERANKER_BATCH_SIZE` | `64` (GPU) | Pares (query, passage) por batch. |
| `RERANKER_MIN_SCORE` | `0.35` | Umbral mínimo de score (probabilidad [0,1]). |
| `RERANKER_MIN_SCORE_FALLBACK_TO_TOPK` | `true` | Si nada supera el umbral, devuelve top-k sin filtrar (evita resultado vacío). |
| `RERANKER_MAX_LENGTH` | `1024` | Largo máx del par (query, passage). Dimensionado para que el passage **contextualizado** (prefijo ~500t + chunk ~512t) no se trunque. |

## Detalles de correctitud

- **Score en [0,1] explícito**: se pasa `activation_fn=torch.nn.Sigmoid()` a `predict`. Así el
  `min_score` es un umbral de probabilidad estable, sin depender del default implícito de
  sentence-transformers ni de la config del modelo.
- **Degradación elegante**: si el `predict` falla, se cae al orden original (top-k) — el reranking
  nunca rompe la query. Re-lanza `MemoryError`/`SystemExit`/`KeyboardInterrupt`.
- **Métricas**: top score por query y conteo de fallbacks (`retrieval_top_rerank_score`,
  `retrieval_rerank_fallback_total`).

## Uso

- **`fragment_query_service`** (RAG): rerankea sobre `contextualized_content or content` →
  el cross-encoder ve la misma representación contextualizada que las lanes de retrieval.
- **`document_search_service`**: rerankea sobre `content` **crudo** (la búsqueda a nivel documento
  es raw-only por diseño).
