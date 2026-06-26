# Contextual Retrieval (representación dual)

El servicio implementa **Contextual Retrieval** (estilo Anthropic): además del fragment crudo,
cada fragment puede tener una **segunda representación contextualizada** que mejora el recall en
chunks ambiguos.

## Idea

Un chunk aislado pierde contexto ("Lo aumentó un 10%"). La contextualización antepone un prefijo
situacional generado por el LLM a partir del `description`/summary del documento:

```
contextualized_content = contexto_situacional + "\n\n" + content
```

Ese texto se embebe en columnas dedicadas, **sin tocar** el `content`/`vector` originales:
`contextualized_content`, `contextualized_vector VECTOR(1024)`, `contextualized_embedding_identity`,
`contextualization_status`.

> bge-m3 (ventana 8192) hace viable esto: `prefijo(~500t) + chunk(512t) ≈ 1000t` entra sin truncar,
> a diferencia de e5-large (512t) que recortaba el contenido.

## Write path — `ContextualizeFragmentProcessor`

Pertenece al **enrichment** (`DocumentEnrichmentService`, junto con la clasificación de metadata).
Para cada fragment pide al LLM el contexto, lo antepone, lo embebe y persiste.

- **Incremental/idempotente**: solo procesa fragments PENDING en la identidad de embedding activa
  (`_is_already_contextualized`), así re-correr el enrich solo paga lo que falta.
- Concurrente (`CONTEXTUALIZE_FRAGMENT_CONCURRENCY`, default 4) con aislamiento de error por fragment.
- Sin summary del documento → marca `not_required` (skip elegante).

## Read path — `FragmentQueryService` (RRF dual-lane)

`retrieve_context_fragments_by_question` corre hasta **4 lanes** y las fusiona con Reciprocal Rank
Fusion (RRF):

| Lane | Fuente |
| --- | --- |
| `vector_raw` | similitud sobre `vector` |
| `vector_contextual` | similitud sobre `contextualized_vector` |
| `bm25_raw` | BM25 sobre `content` |
| `bm25_contextual` | BM25 sobre `contextualized_content` |

- Las lanes contextuales se gatean con `FRAGMENT_QUERY_CONTEXTUAL_RETRIEVAL_ENABLED` (default `true`).
- Un fragment fuerte en varias lanes recibe boost (RRF); los que no tienen vector contextualizado
  simplemente caen a la lane raw.
- BM25 es **no-fatal**: si falla, se cae a vector-only.
- El **reranker** puntúa sobre `contextualized_content or content` (misma representación que el retrieval).
- Cada retrieval concurrente corre en **su propia sesión DB** (las `AsyncSession` no son seguras
  para uso concurrente).

> El **document-level search** (`document_search_service`) es **raw-only** por diseño.

## Rollout / operación

1. Activar bge-m3 en `.env` (embedder + tokenizers; ver `docs/adapters/embedders.md`).
2. **Bulk enrich** (contextualize) → genera la representación contextualizada.
3. **Bulk reembed** → refresca ambos vectores a la identidad activa.

El identity-gating hace ambos pasos **idempotentes**. El reembed refresca el vector raw y, cuando
existe y está stale, el contextualizado.

## Variables relevantes

| Variable | Default | Descripción |
| --- | --- | --- |
| `FRAGMENT_QUERY_CONTEXTUAL_RETRIEVAL_ENABLED` | `true` | Activa las lanes contextuales. |
| `FRAGMENT_QUERY_SIMILARITY_THRESHOLD` | `0.80` (GPU) | Umbral de similitud coseno. |
| `FRAGMENT_QUERY_BM25_RRF_K` | `60` | Constante `k` del RRF. |
| `CONTEXTUALIZE_FRAGMENT_CONCURRENCY` | `4` | Fragments contextualizados en paralelo. |
| `CONTEXTUALIZE_FRAGMENT_MAX_DOCUMENT_SUMMARY_CHARS` | `2000` | Cap del summary usado como contexto. |
| `LLM_PROVIDER_CONTEXTUALIZE_FRAGMENT_URL` | — | Endpoint del llm-service (`/api/v1/fragment-contextualize`). Requerido. |
