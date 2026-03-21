# Embedders

Este documento describe los distintos embedders implementados para generar vectores de texto.

## 1. HuggingfaceEmbedderAdapter

### 📝 Descripción

- Usa `HuggingFaceEmbeddings` para generar embeddings de documentos y queries.
-Modelo por defecto: `"sentence-transformers/all-MiniLM-L6-v2"`.
-Ideal para pipelines ligeros y rápidos, compatible con español e inglés.

### 📦 Instalación requerida

```bash
pip install langchain-huggingface
pip install sentence-transformers
```

### 📏 Parámetros

| Parámetro    | Significado                                |
| ------------ | ------------------------------------------ |
| `model_name` | Nombre del modelo HuggingFace a usar       |
| `device`     | `"cpu"`, `"cuda"` o `None` para automático |

### ⚠️ Consideraciones

- Genera vectores de 384 dimensiones.
- Compatible con bases de datos de vectores, ajustar esquema a 384.

### 🔄 Modelos alternativos

- `"sentence-transformers/all-MiniLM-L12-v2"`
- `"paraphrase-multilingual-MiniLM-L12-v2"`
- `"sentence-transformers/all-mpnet-base-v2"`

## 2. OllamaEmbedderAdapter

### 📝 Descripción

- Usa `OllamaEmbeddings` para generar vectores de texto.
- Modelo por defecto: `"nomic-embed-text:v1.5"`.
- Ideal para entornos offline o modelos locales Ollama.

### 📦 Instalación requerida

```bash
pip install langchain-ollama
```

### 📏 Parámetros

| Parámetro | Significado          |
| --------- | -------------------- |
| `model`   | Modelo Ollama a usar |

### ⚠️ Consideraciones

- Genera vectores de 768 dimensiones.
- Ajustar esquema de la base de datos a 768.
- Requiere instalación y configuración de Ollama.

### 🔄 Modelos alternativos

- `"nomic-embed-text:v1.5"`
- `"nomic-embed-text:v1.6"`

## 3. SentenceTransformerEmbedderAdapter

### 📝 Descripción

- Usa `SentenceTransformer` para generar embeddings consistentes con modelos SBERT.
- Modelo por defecto: `"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"`.
- Compatible con pipelines multilingües y RAG.

### 📦 Instalación requerida

```bash
pip install sentence-transformers
```

### 📏 Parámetros

| Parámetro | Significado         |
| --------- | ------------------- |
| `model`   | Modelo SBERT a usar |

### ⚠️ Consideraciones

- Genera vectores de 384 dimensiones.
- Ideal para bases de datos de vectores medianos.
- Muy rápido y ligero.

### 🔄 Modelos alternativos

- `"sentence-transformers/all-MiniLM-L6-v2"`
- `"paraphrase-multilingual-MiniLM-L12-v2"`
- `"distiluse-base-multilingual-cased-v2"`

## 4. SpacyEmbedderAdapter

### 📝 Descripción

- Usa SpaCy para generar embeddings basados en vectores de palabras.
- Modelo por defecto: `"es_core_news_sm"`.
- Útil para embeddings rápidos en español, no es semántico profundo.

### 📦 Instalación requerida

```bash
pip install spacy
python -m spacy download es_core_news_sm
```

### 📏 Parámetros

| Parámetro    | Significado         |
| ------------ | ------------------- |
| `model_name` | Modelo SpaCy a usar |

### ⚠️ Consideraciones

- Genera vectores de 96 dimensiones.
- Adecuado para bases de datos ligeras o prototipos rápidos.
- Modelos más grandes (`md` o `lg`) generan vectores más precisos y dimensionales más altas.

### 🔄 Modelos alternativos SpaCy

```bash
python -m spacy download es_core_news_md
python -m spacy download es_core_news_lg
```