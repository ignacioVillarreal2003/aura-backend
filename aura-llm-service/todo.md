Perfecto — ahora estás en el punto donde las mejoras ya no son “básicas”, sino de **arquitectura de RAG serio (nivel tesis/producción)**.
Te dejo una lista **priorizada por impacto real** 👇

---

# 🧠 🔴 NIVEL 1 — Cambios CRÍTICOS (mayor impacto)

## 1. 📄 Chunking por artículo (OBLIGATORIO)

👉 Tu problema actual más grande.

**Qué hacer:**

* Cada chunk = 1 artículo completo
* No cortar listas ni numerales

**Alternativa:**

* chunk + overlap (800 / 150)

**Por qué:**

* Evita respuestas incompletas
* Mejora reasoning del LLM

---

## 2. 🎯 Query basada en keywords (no lenguaje natural)

👉 Ya lo tocaste, pero esto define el retrieval.

**Ejemplo bueno:**

```
requisitos aeronave operar sobrevolar territorio nacional documentación matrícula aeronavegabilidad tripulación comunicaciones
```

**Evitar:**

* “explicaciones”
* “estándares internacionales”
* frases largas

---

## 3. 🚫 Filtro de ruido en retrieval

👉 Estás metiendo AVSEC y rompe todo.

**Soluciones:**

* Threshold de similitud (ej: > 0.75)
* Filtrar por tipo de documento
* Penalizar palabras tipo:

  * “programa”
  * “política”
  * “AVSEC”

---

# 🧠 🟠 NIVEL 2 — Mejora fuerte de calidad

## 4. 🔥 Re-ranking (MUY recomendado)

👉 Esto solo te mejora la calidad muchísimo.

**Cómo funciona:**

1. Traés top 10 (vector DB)
2. Pasás por cross-encoder
3. Elegís top 3–5 reales

**Tools:**

* `bge-reranker-large`
* `cross-encoder/ms-marco`

---

## 5. 🧩 Article-aware retrieval

👉 Clave para normativa.

**Idea:**

* Detectás “Art. 19”
* Expandís automáticamente todo el artículo

**Beneficio:**

* Contexto completo sin depender del chunking

---

## 6. 🔀 Hybrid search (vector + keyword)

👉 Muy útil en documentos legales.

**Combinar:**

* embeddings (semántico)
* BM25 (keyword exacto)

**Por qué:**

* “Art. 19” no lo entiende bien un embedding solo

---

# 🧠 🟡 NIVEL 3 — Robustez del sistema

## 7. 🧪 Evaluación automática (clave para tesis)

Medí:

* ✔️ **Faithfulness** → ¿inventa?
* ✔️ **Completeness** → ¿le faltan cosas?
* ✔️ **Relevance** → ¿usa bien el contexto?

**Tip:**

* usá preguntas tipo las que ya generamos

---

## 8. 🧠 Self-check del LLM

Después de responder:

```text
¿La respuesta incluye información que no está en el contexto?
```

👉 Si sí → regenerar

---

## 9. 🧹 Limpieza de contexto antes del LLM

Antes de enviar:

* eliminar basura tipo:

  * encabezados
  * apéndices
  * texto institucional irrelevante

👉 Reduce alucinaciones indirectas

---

# 🧠 🔵 NIVEL 4 — Nivel avanzado (muy pro)

## 10. 🧠 Multi-step retrieval

En vez de:

👉 1 búsqueda

Hacés:

1. Buscar artículo principal
2. Expandir artículos relacionados
3. Re-consultar si falta info

---

## 11. 🧾 Clasificación de chunks

Etiquetar chunks como:

* `requisitos`
* `definición`
* `procedimiento`
* `sanción`

👉 Luego filtrar según la pregunta

---

## 12. 🎯 Prompt dinámico según tipo de pregunta

Detectar si es:

* “qué es” → definiciones
* “qué requisitos” → listas
* “qué pasa si” → sanciones

👉 ajustar prompt automáticamente

---

# 🧠 🟢 NIVEL 5 — Extras (te suman puntos en tesis)

## 13. 📚 Citas estructuradas

Ej:

```
(Art. 19, Código Aeronáutico)
```

---

## 14. 📊 Score de confianza

Mostrar:

* alta / media / baja

---

## 15. 🔎 Highlight de contexto usado

👉 UX + trazabilidad (muy bueno para FAU)

---

# 🚀 Roadmap recomendado (orden real)

Si lo implementás en orden:

1. ✅ Chunking por artículo
2. ✅ Query por keywords
3. ✅ Filtro de ruido
4. 🔥 Re-ranking
5. 🔥 Hybrid search
6. 🧠 Article expansion

---

# 🧠 Conclusión clave

Ahora mismo estás en:

> 🟡 “RAG correcto pero incompleto”

Con estos cambios podés llegar a:

> 🟢 “RAG confiable, robusto y defendible en tesis”

---

Si querés, siguiente paso te puedo:

👉 diseñar la **arquitectura completa (diagrama + código base)**
👉 o armarte un **pipeline óptimo con FastAPI + LangChain/LlamaIndex**

Ahí ya lo llevás a nivel profesional de verdad.
