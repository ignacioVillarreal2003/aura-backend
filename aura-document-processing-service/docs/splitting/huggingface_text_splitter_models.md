# Modelos del Text Splitter semántico (HuggingFace)

El splitter semántico (`SemanticChunker`) usa un modelo de embeddings para detectar los cortes.
Por defecto comparte el **mismo modelo que el embedder** (`BAAI/bge-m3`) para no cargar dos copias
en VRAM. Se configura con `TEXT_SPLITTER_HUGGINGFACE_MODEL`.

## BAAI/bge-m3 (default)

Modelo de retrieval multilingüe de referencia (Beijing Academy of AI). Es el default tanto del
embedder como del tokenizer de Docling y del splitter semántico.

| Feature | Value |
| --- | --- |
| Parameters | 570M |
| Context | 8192 tokens |
| Embedding dimension | 1024 |
| Architecture | XLM-RoBERTa |
| Size | ~2.3GB |

**Por qué para chunking:** al compartir el modelo del embedder, el cálculo de breakpoints semánticos
usa exactamente la misma representación que luego indexará el fragment → cortes coherentes con el
espacio de retrieval, sin coste extra de VRAM.

## Alternativas (configurables)

| Modelo | Dim | Context | Notas |
| --- | --- | --- | --- |
| `intfloat/multilingual-e5-large` | 1024 | 512 | Requiere prefijos `query:`/`passage:`; ventana corta. |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | 128 | Más liviano; menor calidad multilingüe. |

> Si se cambia el modelo del splitter sin alinear los parámetros del embedder, se pierde el
> compartido de instancia (se cargarían dos modelos). Mantener `model/device/normalize/max_seq/dtype`
> iguales en `TEXT_SPLITTER_HUGGINGFACE_*` y `EMBEDDER_HUGGINGFACE_*`.
