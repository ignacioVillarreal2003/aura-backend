# Text Splitters

Dividen el documento en fragments (chunks). Arquitectura de **dos niveles** seleccionada por
`TEXT_SPLITTER_*` vía `TextSplitterFactory`:

- **Activo**: `docling_hybrid` (default) — chunking **estructura-aware**, basado en archivo.
- **Fallback flat-text** (`TEXT_SPLITTER_STRUCTURED_FALLBACK_TYPE`, default `huggingface`): si
  Docling no está disponible o falla, la ingestión **lee → limpia → splittea** con el splitter plano.

El validador exige no-vacío el modelo/tokenizer del tipo efectivo según `active_type`.

## 1. docling_hybrid (default, estructura-aware)

Usa el `HybridChunker` de Docling con tokenizer **`BAAI/bge-m3`**. Convierte el archivo, respeta
la estructura (headings, tablas, secciones) y produce chunks con **provenance rica**: `page_number`,
`section_path`, `heading`, `char_start/end`, `bbox`. Además genera un `embed_text` contextualizado
por headings (lo que el embedder usa para el vector).

| Variable | Default |
| --- | --- |
| `TEXT_SPLITTER_DOCLING_TOKENIZER_MODEL` | `BAAI/bge-m3` |
| `TEXT_SPLITTER_DOCLING_MAX_TOKENS` | `512` |
| `TEXT_SPLITTER_DOCLING_MERGE_PEERS` | `true` |
| `TEXT_SPLITTER_DOCLING_DEVICE` | `auto` |
| `TEXT_SPLITTER_DOCLING_NUM_THREADS` | `4` |

> `chunk_file` serializa las conversiones (lock) porque los modelos de Docling no son thread-safe.

## 2. huggingface (semántico, fallback flat-text)

Usa `SemanticChunker` (langchain-experimental) con embeddings **`BAAI/bge-m3`**: detecta cortes por
distancia semántica entre oraciones. Pre-segmenta en ventanas para acotar el costo, fuerza el límite
de tokens por chunk (sub-split) y mergea chunks cortos respetando el cap de tokens.

| Variable | Default |
| --- | --- |
| `TEXT_SPLITTER_HUGGINGFACE_MODEL` | `BAAI/bge-m3` |
| `TEXT_SPLITTER_HUGGINGFACE_DEVICE` | `cuda` |
| `TEXT_SPLITTER_HUGGINGFACE_MAX_SEQ_LENGTH` | `8192` |
| `TEXT_SPLITTER_HUGGINGFACE_TORCH_DTYPE` | `auto` |
| `TEXT_SPLITTER_HUGGINGFACE_BREAKPOINT_THRESHOLD_TYPE` | `percentile` |
| `TEXT_SPLITTER_HUGGINGFACE_MAX_CHUNK_TOKENS` | `510` |
| `TEXT_SPLITTER_HUGGINGFACE_CHUNK_TOKEN_OVERLAP` | `50` |

> **Instancia compartida**: sus parámetros de embedding (model/device/normalize/max_seq/dtype)
> espejan los del `EmbedderSettings`, así que **comparte la instancia bge-m3 del embedder** en VRAM
> en lugar de cargar una segunda copia.

## 3. recursive (tiktoken)

`RecursiveCharacterTextSplitter` por tokens (encoding `cl100k_base`). Splitter plano de respaldo,
rápido y sin modelos.

| Variable | Default |
| --- | --- |
| `TEXT_SPLITTER_RECURSIVE_SPLIT_SIZE` | `512` |
| `TEXT_SPLITTER_RECURSIVE_SPLIT_OVERLAP` | `50` |
| `TEXT_SPLITTER_RECURSIVE_ENCODING_NAME` | `cl100k_base` |

## Común

| Variable | Default | Descripción |
| --- | --- | --- |
| `TEXT_SPLITTER_ACTIVE_TYPE` | `docling_hybrid` | Tipo activo. |
| `TEXT_SPLITTER_STRUCTURED_FALLBACK_TYPE` | `huggingface` | Fallback plano (no puede ser `docling_hybrid`). |
| `TEXT_SPLITTER_MAX_TEXT_LENGTH` | `10000000` | Máximo de caracteres. |
| `TEXT_SPLITTER_MIN_CHUNK_CHARS` | `150` | Mergea chunks por debajo de este largo. |

> Los chunks se mantienen ~512 tokens aunque bge-m3 soporte 8192: granularidad chica = mejor
> precisión de retrieval. El `embed_text`/contextualización agregan contexto sin agrandar el chunk.
