# Text Splitters

Este documento describe los distintos text splitters implementados.

## 1. RecursiveTextSplitterAdapter

### 📝 Descripción

- `RecursiveTextSplitterAdapter` usa `RecursiveCharacterTextSplitter` con tokenización basada en tiktoken según un modelo (por defecto `"gpt-4"`).
- Divide el texto siguiendo una jerarquía de separadores (párrafos → oraciones → palabras → caracteres).
- Es el splitter estándar para pipelines RAG.

### 📦 Instalación requerida

```bash
pip install langchain-text-splitters
pip install tiktoken
```

### 📏 Parámetros

| Parámetro | Significado                    |
| --------- | ------------------------------ |
| `size`    | tamaño del chunk en tokens |
| `overlap` | tokens solapados entre chunks  |

### ⚠️ Consideraciones

- Respeta estructura semántica básica, no es semántico puro.
- El `chunk_size` depende del modelo (`gpt-4` ≈ 128k tokens máx).
- Muy eficiente para cualquier tipo de texto.

### 🔄 Modelos alternativos

- `"gpt-4"`
- `"gpt-4o"`
- `"gpt-4o-mini"`
- `"gpt-3.5-turbo"`
- `"text-embedding-3-large"`

## 2. SemanticTextSplitterAdapter

### 📝 Descripción

Utiliza `SemanticChunker`, que genera chunks basados en cambios semánticos calculando embeddings y detectando rupturas estadísticamente (percentiles, desviación estándar, etc.).
Ideal para mantener coherencia lógica en documentos extensos.

### 📦 Instalación requerida

```bash
pip install langchain-experimental
pip install sentence-transformers
pip install langchain-huggingface
```

### 📏 Parámetros

Este splitter no utiliza directamente `size` ni `overlap`.
Determina los cortes según distancias semánticas entre oraciones.

### ⚠️ Consideraciones

- Requiere más CPU/GPU por cálculo de embeddings.
- Muy bueno para manuales técnicos, doctrina, PDFs complejos.

### 🔄 Modelos alternativos

- `"sentence-transformers/all-MiniLM-L6-v2"`

Livianos:

- `"sentence-transformers/all-MiniLM-L12-v2"`
- `"paraphrase-MiniLM-L3-v2"`

Más potentes:

- `"sentence-transformers/all-mpnet-base-v2"`
- `"intfloat/multilingual-e5-large"`

## 3. SpacyTextSplitterAdapter

### 📝 Descripción

Splitter basado en SpaCy que usa análisis NLP real para dividir el texto según oraciones y tokens del modelo SpaCy.
Extremadamente preciso para documentos en español.

### 📦 Instalación requerida

```bash
pip install spacy
pip install langchain-text-splitters
python -m spacy download es_core_news_sm
```

### 📏 Parámetros

| Parámetro | Significado                                   |
| --------- | --------------------------------------------- |
| `size`    | cantidad aproximada de tokens SpaCy por chunk |
| `overlap` | cantidad de tokens superpuestos               |

### ⚠️ Consideraciones

- Los tamaños dependen de tokenizer de SpaCy, no de tiktoken.
- `es_core_news_sm` funciona, pero los modelos md y lg dan mejores cortes.

### 🔄 Modelos alternativos SpaCy

```bash
python -m spacy download es_core_news_sm
python -m spacy download es_core_news_md
python -m spacy download es_core_news_lg
```

## 4. SentenceTransformerTextSplitterAdapter

### 📝 Descripción

Utiliza `SentenceTransformersTokenTextSplitter`, que divide el texto según tokens del modelo de embeddings de Sentence Transformers.
Útil cuando el pipeline usa el mismo modelo para embeddings (ej. `all-mpnet-base-v2`).

### 📦 Instalación requerida

```bash
pip install sentence-transformers
pip install langchain-text-splitters
```

### 📏 Parámetros

| Parámetro | Significado                          |
| --------- | ------------------------------------ |
| `size`    | tokens por chunk del tokenizer SBERT |
| `overlap` | tokens superpuestos                  |

### ⚠️ Consideraciones

- Mantiene coherencia con embeddings del mismo modelo.
- Excelente para pipelines donde la uniformidad del embedding es crítica.
- Más pesado que un tokenizer simple.

### 🔄 Modelos alternativos

- `"sentence-transformers/all-mpnet-base-v2"`
- `"sentence-transformers/all-MiniLM-L6-v2"` (más rápido)
- `"distiluse-base-multilingual-cased-v2"` (multilingüe)
- `"paraphrase-mpnet-base-v2"` (muy preciso)

## 5. TokenTextSplitterAdapter

### 📝 Descripción

Splitter mínimo y rápido basado únicamente en tokens.
No utiliza semántica ni análisis lingüístico. Ideal para PDFs convertidos sin estructura o textos extremadamente grandes.

### 📦 Instalación requerida

```bash
pip install langchain-text-splitters
```

### 📏 Parámetros

| Parámetro | Significado                  |
| --------- | ---------------------------- |
| `size`    | cantidad de tokens por chunk |
| `overlap` | tokens superpuestos          |

### ⚠️ Consideraciones

- No preserva oraciones.
- Es el más estable y rápido de todos.
- Excelente para chunking masivo previo a embeddings.

### 🔄 Modelos alternativos de tokenizer

Podrías elegir un tokenizer distinto si necesitás compatibilidad:

- `"cl100k_base"` (OpenAI actual)
- `"gpt2"`
- `"o200k_base"` (modelos 2024–2025 de alta capacidad)

## 6. CharTextSplitterAdapter

### 📝 Descripción

- Splitter basado en `CharacterTextSplitter` que divide texto según un separador fijo (por defecto `\n`).
- Es simple, rápido y útil cuando el texto ya está estructurado en líneas o párrafos. 
- No realiza tokenización ni análisis semántico.

### 📦 Instalación requerida

```bash
pip install langchain-text-splitters
```

### 📏 Parámetros

| Parámetro | Significado                          |
| --------- | ------------------------------------ |
| `size`    | cantidad de caracteres por chunk     |
| `overlap` | caracteres superpuestos entre chunks |

### ⚠️ Consideraciones

- Depende del separador definido; si el texto no tiene `\n` o separadores claros, puede generar un único chunk grande.
- No preserva semántica ni analiza oraciones.
- Muy rápido y ligero para textos ya bien estructurados.

## 7. CharTiktokenTextSplitterAdapter

### 📝 Descripción

- Versión de `CharacterTextSplitter` que utiliza tiktoken para medir el tamaño de los chunks en tokens en lugar de caracteres.
- Permite mayor compatibilidad con modelos de OpenAI y pipelines de embeddings.

### 📦 Instalación requerida

```bash
pip install langchain-text-splitters
pip install tiktoken
```

### 📏 Parámetros

| Parámetro | Significado                      |
| --------- | -------------------------------- |
| `size`    | cantidad de tokens por chunk     |
| `overlap` | tokens superpuestos entre chunks |

### ⚠️ Consideraciones

- Depende de `separator="\n"`; si el texto no contiene saltos de línea, puede generar un solo chunk.
- Mantener saltos de línea o usar `separator=" "` mejora la división.
- Ideal cuando se desea alinear chunking con conteo de tokens de modelo.

### 🔄 Modelos alternativos

- `"cl100k_base"` (OpenAI actual)
- `"o200k_base"` (modelos 2024–2025)
- `"gpt2"` (tokenizer clásico)

## 8. HuggingfaceTextSplitterAdapter

### 📝 Descripción

- Splitter que usa `CharacterTextSplitter` junto a un tokenizer de HuggingFace (por ejemplo `GPT2TokenizerFast`).
- Corta los chunks según tokens del tokenizer, pero respeta el separador definido (`\n`).

### 📦 Instalación requerida

```bash
pip install transformers
pip install langchain-text-splitters
```

### 📏 Parámetros

| Parámetro | Significado                      |
| --------- | -------------------------------- |
| `size`    | cantidad de tokens por chunk     |
| `overlap` | tokens superpuestos entre chunks |

### ⚠️ Consideraciones

- También depende de `separator="\n"`; si el texto tiene saltos de línea excesivos o pocos, los chunks pueden quedar desbalanceados.
- Útil si tu pipeline de embeddings utiliza tokenizers específicos de HuggingFace.
- Compatible con cualquier modelo de tokenizer HuggingFace que soporte `from_pretrained`.

### 🔄 Modelos alternativos

- `"gpt2"`
- `"gpt2-medium"`
- `"EleutherAI/gpt-neo-125M"`
- `"distilgpt2"`