Text cleaner::::
Errores OCR (0 por o, 4 por a) → eso es corrección semántica, otro componente.
Palabras separadas (docu mento) → requiere NLP/diccionario.
Deduplicación de párrafos → corresponde al pipeline de indexado, no al cleaner.






# Prontos para revision

# 🔥 PRIORIDAD 1 — BLOQUEANTES PARA PRODUCCIÓN (resolver sí o sí)

1. **User ID hardcodeado**

* Riesgo: seguridad, auditoría, multiusuario roto
* Acción: JWT → extraer user_id → propagar a servicios y repositorios

2. **Sesión de BD compartida en Background Tasks**

* Riesgo: errores intermitentes en prod (`Session closed`)
* Acción: background task crea su propia sesión (no pasar `db`)






# 🔥 PRIORIDAD 1 — BLOQUEANTES PARA PRODUCCIÓN (resolver sí o sí)



3. **Falta de retry logic (MinIO / DB / embeddings)**

* Riesgo: documentos perdidos por fallos transitorios
* Acción: reintentos con backoff (tenacity)

4. **Limpieza incompleta de archivos temporales**

* Riesgo: fuga de disco
* Acción: `try/finally` o `tempfile` desde el inicio

5. **CORS inseguro por defecto (`*`)**

* Riesgo: exposición de API
* Acción: defaults restrictivos + validación en prod

---

## 🔐 PRIORIDAD 2 — SEGURIDAD Y ABUSO

6. **Sin autenticación ni autorización**

* Riesgo: cualquiera accede a todo
* Acción: dependency `get_current_user` + ownership checks

7. **Validación de inputs insuficiente**

* Riesgo: path traversal, archivos maliciosos
* Acción: sanitizar filenames, validar extensiones reales

8. **Sin rate limiting**

* Riesgo: DoS, abuso de recursos
* Acción: slowapi / Redis

9. **Logs con información sensible**

* Riesgo: leak de paths y estructura interna
* Acción: en prod no usar tracebacks completos

---

## ⚙️ PRIORIDAD 3 — ESTABILIDAD Y PERFORMANCE

10. **Factories sin thread safety**

* Riesgo: race conditions bajo carga
* Acción: locks o inicializar en startup

11. **Operaciones blocking en funciones async**

* Riesgo: event loop bloqueado
* Acción: `asyncio.to_thread` o mover a task queue

12. **Sin idempotencia en creación**

* Riesgo: documentos duplicados
* Acción: `idempotency_key`

13. **Sin límites de fragmentación**

* Riesgo: consumo masivo de memoria / BD
* Acción: `max_fragments` + procesamiento en batches

---

## 📊 PRIORIDAD 4 — OBSERVABILIDAD Y OPERACIÓN

14. **Health check falso (siempre healthy)**

* Riesgo: Kubernetes/Docker no detecta fallos
* Acción: separar liveness / readiness reales

15. **Sin métricas**

* Riesgo: no sabés qué pasa en prod
* Acción: Prometheus + métricas clave (tiempos, fallos)

16. **Logging sin correlación**

* Riesgo: debugging imposible
* Acción: request_id + document_id en logs

---

## 🧪 PRIORIDAD 5 — CALIDAD Y MADUREZ

17. **DTOs con validaciones pobres**

* Riesgo: errores lógicos silenciosos
* Acción: validators Pydantic

18. **Mensajes de error inconsistentes (ES)**

* Riesgo: API poco profesional
* Acción: errores en inglés + códigos

19. **Sin tests**

* Riesgo: regresiones constantes
* Acción mínima: unit + integration tests

20. **Secrets en texto plano**

* Riesgo: filtraciones
* Acción: secrets manager / variables seguras

21. **Sin graceful shutdown**

* Riesgo: documentos cortados a mitad
* Acción: manejar SIGTERM/SIGINT

---
