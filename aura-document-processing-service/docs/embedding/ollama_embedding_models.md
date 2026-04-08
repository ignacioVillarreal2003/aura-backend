# Modelos de Embedding de Ollama

## Qwen3

Modelo de embeddings basado en la serie Qwen3.

**Características principales**

- Multilingüe (100+ idiomas)
- Soporte para textos largos
- Buen rendimiento en tareas de retrieval y ranking
- Diferentes tamaños de modelo disponibles

**Modelos disponibles**

| Model                | Size  | Context | Dimensions |
|----------------------|-------|---------|------------|
| qwen3-embedding:0.6b | 639MB | 32K     | 1024       |
| qwen3-embedding:4b   | 2.5GB | 40K     | 2560       |
| qwen3-embedding:8b   | 4.7GB | 40K     | 4096       |

---

## nomic-embed-text-v2-moe

Modelo de embeddings optimizado para **multilingual retrieval**.

**Características principales**

* Arquitectura **Mixture of Experts (MoE)**
* Muy buen rendimiento en benchmarks de retrieval
* Soporte multilingüe (~100 idiomas)
* Embeddings comprimibles con **Matryoshka representation**

**Especificaciones**

| Feature             | Value           |
|---------------------|-----------------|
| Parameters          | 475M            |
| Active params       | 305M            |
| Context             | 512 tokens      |
| Embedding dimension | 768             |
| Architecture        | MoE (8 experts) |

---

## nomic-embed-text

Modelo clásico de embeddings de Nomic.

**Características principales**

* Modelo liviano
* Buen rendimiento general
* Contexto más largo que v2

**Especificaciones**

| Model            | Size  | Context | Dimensions |
|------------------|-------|---------|------------|
| nomic-embed-text | 274MB | 2K      | **768**    |

---
