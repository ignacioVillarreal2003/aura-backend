# Modelos de Embedding de Ollama

## Qwen3

Modelo de embeddings basado en la serie Qwen3.

**Características principales**

- Multilingüe (100+ idiomas)
- Soporte para textos largos
- Buen rendimiento en tareas de retrieval y ranking
- Diferentes tamaños de modelo disponibles

**Modelos disponibles**

| Model | Size | Context |
|------|------|------|
| qwen3-embedding:0.6b | 639MB | 32K |
| qwen3-embedding:4b | 2.5GB | 40K |
| qwen3-embedding:8b | 4.7GB | 40K |

**Embedding dimension**

- configurable hasta **4096**

**Instalación**

```bash
ollama pull qwen3-embedding
````

---

## nomic-embed-text-v2-moe

Modelo moderno de embeddings optimizado para **multilingual retrieval**.

**Características principales**

* Arquitectura **Mixture of Experts (MoE)**
* Muy buen rendimiento en benchmarks de retrieval
* Soporte multilingüe (~100 idiomas)
* Embeddings comprimibles con **Matryoshka representation**

**Especificaciones**

| Feature             | Value           |
| ------------------- | --------------- |
| Parameters          | 475M            |
| Active params       | 305M            |
| Context             | 512 tokens      |
| Embedding dimension | 768 → 256       |
| Architecture        | MoE (8 experts) |

**Instalación**

```bash
ollama pull nomic-embed-text-v2-moe
```

---

## nomic-embed-text

Modelo clásico de embeddings de Nomic.

**Características principales**

* Modelo liviano
* Buen rendimiento general
* Contexto más largo que v2

**Especificaciones**

| Feature  | Value                        |
| -------- | ---------------------------- |
| Size     | 274MB                        |
| Context  | 2K tokens                    |
| Use case | prototipos y pruebas rápidas |

**Instalación**

```bash
ollama pull nomic-embed-text
```

# Resultados

Resultados de pruebas internas de recuperación semántica.

- **qwen3-embedding**: El modelo con mejores resultados en recuperación semántica, aunque requiere mayor consumo de recursos.
- **nomic-embed-text-v2-moe**: Ofrece resultados aceptables para pruebas y entornos con recursos limitados, pero presenta algunas limitaciones en calidad de recuperación.
- **nomic-embed-text**: Modelo funcional para pruebas básicas, pero su desempeño es inferior y no resulta suficiente para escenarios más exigentes.