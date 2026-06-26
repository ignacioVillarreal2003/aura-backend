# Embedders

Generan los vectores de los fragmentos (al ingestar) y de las queries (al buscar).
Se seleccionan por configuración (`EMBEDDER_*`) vía `EmbedderFactory` (lazy, thread-safe).

Backends disponibles: **`huggingface`** (default, recomendado en prod/GPU) y **`ollama`**.

## Configuración común (`EMBEDDER_`)

| Variable | Default | Descripción |
| --- | --- | --- |
| `EMBEDDER_ACTIVE_TYPE` | `huggingface` | Backend activo (`huggingface` \| `ollama`). |
| `EMBEDDER_VECTOR_DIMENSION` | `1024` | Dimensión del vector. **Debe** coincidir con el modelo y con la columna `pgvector`. El validador la exige no-nula. |
| `EMBEDDER_MAX_BATCH_SIZE` | `128` (GPU) | Máximo de textos por batch. |
| `EMBEDDER_MAX_BATCH_TOKENS` | `131072` | Presupuesto de tokens por batch (`count × longest_padded`). El batch se auto-reduce con inputs largos para acotar VRAM; `0` lo desactiva. |
| `EMBEDDER_MAX_TEXT_LENGTH` | `8000` | Máximo de caracteres por texto. |

Resiliencia (ambos backends): **retry con backoff** (tenacity) + **circuit breaker** (aiobreaker)
controlado por `EMBEDDER_MAX_RETRIES`, `EMBEDDER_RETRY_DELAY/RETRY_MAX_DELAY`,
`EMBEDDER_CIRCUIT_BREAKER_THRESHOLD/TIMEOUT`.

## 1. HuggingFaceEmbedder (default)

Usa `HuggingFaceEmbeddings` (Sentence Transformers) con modelo por defecto **`BAAI/bge-m3`**
(multilingüe, 1024-dim, ventana 8192 tokens).

| Variable | Default | Descripción |
| --- | --- | --- |
| `EMBEDDER_HUGGINGFACE_MODEL` | `BAAI/bge-m3` | Cualquier modelo de Sentence Transformers. |
| `EMBEDDER_HUGGINGFACE_DEVICE` | `cuda` | `cpu` \| `cuda`. |
| `EMBEDDER_HUGGINGFACE_NORMALIZE_EMBEDDINGS` | `true` | L2-normaliza los vectores. |
| `EMBEDDER_HUGGINGFACE_MAX_SEQ_LENGTH` | `8192` | Ventana de tokens (aprovecha bge-m3 completo; evita truncar `prefijo+chunk` en contextual retrieval). |
| `EMBEDDER_HUGGINGFACE_TORCH_DTYPE` | `auto` | `auto` (bfloat16 en GPU Ampere+, float16 en CUDA viejo, float32 en CPU), o explícito. |
| `EMBEDDER_HUGGINGFACE_QUERY_INSTRUCTION` | `""` | Prefijo de query. **Vacío para bge-m3** (no usa prefijos, a diferencia de e5). |
| `EMBEDDER_HUGGINGFACE_EMBED_INSTRUCTION` | `""` | Prefijo de passage. **Vacío para bge-m3**. |

**Caché de modelo compartida** (`_hf_model_cache`): la instancia de bge-m3 se cachea por
`(model, device, normalize, token, max_seq_length, dtype)`. El *text splitter semántico* usa
los mismos parámetros, así que **comparten una sola instancia en VRAM** (no se carga dos veces).
El lock de inferencia por modelo serializa el trabajo en GPU (evita contención/OOM).

## 2. OllamaEmbedder

Usa `OllamaEmbeddings` contra un servidor Ollama. Útil en CPU / entornos sin GPU.

| Variable | Default | Descripción |
| --- | --- | --- |
| `EMBEDDER_OLLAMA_MODEL` | `qwen3-embedding:0.6b` | Modelo de Ollama (1024-dim). |
| `EMBEDDER_OLLAMA_URL` | `http://localhost:11434` | URL del servidor. |
| `EMBEDDER_OLLAMA_REQUEST_TIMEOUT` | `60` | Timeout por request (s). |

## Robustez (production-hardening)

- **Inputs vacíos no rompen el batch**: un texto blank/empty se reemplaza por un placeholder
  (preserva el conteo de salida, que los callers asumen `len(embeddings) == len(texts)`).
- **Over-length**: textos sobre `max_text_length` se truncan (no se descarta el batch).
- **Batching por tokens**: además del cap por count, se respeta `max_batch_tokens` → el batch
  se achica con inputs largos para acotar VRAM.
- **OOM de CUDA excluido del retry**: reintentar el mismo batch tras un out-of-memory no recupera;
  falla de inmediato en vez de gastar reintentos.
- **Guard NaN/Inf**: nunca se persiste un vector no-finito (envenenaría la búsqueda pgvector);
  si el modelo produce NaN/Inf se lanza excepción con sugerencia de usar `bfloat16`/`float32`.

## Notas operativas

- bge-m3 = **1024-dim** → no requiere migración de columna respecto a e5-large (misma dimensión),
  pero los vectores **no son intercambiables** semánticamente: cambiar de modelo requiere re-embed.
- La identidad de embedding (`active_embedding_identity`) incluye el modelo, normalize, max_seq y
  las instrucciones → el re-embed detecta automáticamente qué fragmentos están stale.
