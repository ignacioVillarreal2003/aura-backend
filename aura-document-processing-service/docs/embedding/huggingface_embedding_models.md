# Modelos de Embedding de HuggingFace (Sentence Transformers)

## paraphrase-multilingual-MiniLM-L12-v2

Modelo multilingüe liviano de la familia MiniLM, optimizado para similitud semántica y paráfrasis.

**Características principales**

- Multilingüe (50+ idiomas incluyendo español)
- Muy liviano y rápido en CPU
- Buena relación rendimiento/recursos
- Ideal para entornos con recursos limitados

**Especificaciones**

| Feature             | Value     |
| ------------------- | --------- |
| Parameters          | 118M      |
| Context             | 128 tokens|
| Embedding dimension | 384       |
| Architecture        | MiniLM-L12|
| Size                | ~470MB    |

---

## BAAI/bge-m3

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
