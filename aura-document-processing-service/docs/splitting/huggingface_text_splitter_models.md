# Modelos de Chunking de HuggingFace (Sentence Transformers)

## sentence-transformers/all-MiniLM-L6-v2

Modelo de embeddings liviano de la familia Sentence Transformers, pensado para generar vectores semánticos a partir de oraciones y párrafos cortos.

**Características principales**

* Diseñado para encoder de oraciones y párrafos cortos
* Muy rápido en GPU y CPU
* Baja latencia → ideal para chunking en tiempo real
* Buen baseline semántico

**Especificaciones**

| Feature                | Value                              |
| ---------------------- | ---------------------------------- |
| Dimensión de embedding | 384                                |
| Arquitectura base      | MiniLM-L6-H384                     |
| Contexto efectivo      | ~256 tokens                        |
| Tipo de uso            | Sentence / short paragraph encoder |
| Tamaño aproximado      | ~90MB                              |

---

## intfloat/multilingual-e5-base

Modelo de embeddings de Microsoft optimizado para retrieval semántico multilingüe con mejor comprensión contextual que MiniLM.

**Características principales**

* Multilingüe (muy importante para español)
* Mejor captura de contexto semántico
* Ideal para tareas tipo RAG
* Requiere prefijos (`query:` / `passage:`) para máximo rendimiento

**Especificaciones**

| Feature                | Value               |
| ---------------------- | ------------------- |
| Dimensión de embedding | 768                 |
| Arquitectura base      | XLM-RoBERTa         |
| Contexto               | 512 tokens          |
| Tipo de uso            | Retrieval semántico |
| Tamaño aproximado      | ~1.1GB              |

---
