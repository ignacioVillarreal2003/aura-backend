# Modelos de Embedding de HuggingFace (Sentence Transformers)

> **Default actual: `BAAI/bge-m3`** (1024-dim). Es el modelo recomendado y el que usan por defecto
> el embedder, el tokenizer de Docling y el splitter semántico.

## BAAI/bge-m3 (default)

Modelo de la familia BGE de Beijing Academy of AI, referente actual en retrieval multilingüe.

**Características principales**

- Multilingüe (100+ idiomas)
- Soporta **dense**, **sparse** y **multi-vector** retrieval simultáneamente
- Excelente rendimiento en benchmarks MTEB
- Contexto muy largo

**Especificaciones**

| Feature             | Value        |
| ------------------- | ------------ |
| Parameters          | 570M         |
| Context             | 8192 tokens  |
| Embedding dimension | 1024         |
| Architecture        | XLM-RoBERTa  |
| Size                | ~2.3GB       |

---

## intfloat/multilingual-e5-large

Modelo de la familia E5 de Microsoft, entrenado específicamente para retrieval multilingüe con instrucciones.

**Características principales**

- Multilingüe (100+ idiomas)
- Requiere prefijo `query:` / `passage:` para mejores resultados
- Muy buen rendimiento en tareas de retrieval asimétrico
- Balance sólido entre tamaño y calidad

**Especificaciones**

| Feature             | Value       |
| ------------------- | ----------- |
| Parameters          | 560M        |
| Context             | 512 tokens  |
| Embedding dimension | 1024        |
| Architecture        | XLM-RoBERTa |
| Size                | ~2.2GB      |

---
