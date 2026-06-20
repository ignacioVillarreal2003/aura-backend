# AURA Document Processing Service — Revisión Global de Arquitectura

> **Tipo de documento:** Reporte de auditoría / code review global (Staff Eng + Architect).
> **Alcance:** Revisión exhaustiva de todo el repositorio a nivel sistema.
> **Acción ejecutada:** Solo análisis. **No se modificó ningún archivo de código.** Este documento es el entregable.
> **Fecha:** 2026-06-20 · **Rama analizada:** `document-pro`

---

## 0. Resumen ejecutivo

Este es un servicio de procesamiento de documentos (ingesta → lectura → limpieza → chunking → embedding → indexado vectorial/BM25 → enriquecimiento LLM → grafo de conocimiento) construido sobre **FastAPI + SQLAlchemy async + PostgreSQL/pgvector + Redis + RabbitMQ + MinIO + Neo4j**.

**Veredicto general:** el proyecto está **notablemente cerca de "production-ready"** y muy por encima de la media. La Clean Architecture es real (no decorativa), la inyección de dependencias es explícita y con rollback, hay invariantes de producción, logging estructurado JSON, manejo de errores centralizado, outbox para publicación confiable, idempotencia con locks en Redis, soft-deletes y consultas parametrizadas. **No se detectaron bugs críticos ni vulnerabilidades de inyección.**

Los hallazgos relevantes son **de proceso e higiene del repositorio**, no de diseño del runtime:

| Severidad | Cantidad | Tema principal |
|-----------|----------|----------------|
| 🔴 Crítico | 0 | — |
| 🟠 Alto | 3 | Secretos versionados en git, ausencia de `.gitignore`, ausencia de CI |
| 🟡 Medio | 5 | Cobertura de tests, DRY en requirements, observabilidad de negocio, README inexistente, rate-limit no configurable |
| 🟢 Bajo | 6 | Detalles menores (ver sección 4) |

---

## 1. Fotografía del sistema

### Estructura (Clean Architecture, 4 capas bien delimitadas)

```
app/
├── api/               # Capa de entrada: controllers (thin), schemas, handlers, openapi, dependencies, rate limiter
├── application/       # Casos de uso: services, processors (readers/embedders/splitters/rerankers/cleaners), authorization
├── domain/            # DTOs, constantes, entidades de autenticación, field_limits (núcleo sin dependencias de framework)
└── infrastructure/    # Adaptadores: persistence (db/graph/memory/storage), http (providers), messaging (rabbitmq)
```

- **~357 archivos Python**, ~27k LOC.
- Patrón consistente: cada controller/service/repository vive en su carpeta con su `interfaces/` (puerto) y sus `exceptions/`.
- Entrypoint: `app/main.py` (`create_app()` + `lifespan`).

### Stack y dependencias
- Web: FastAPI 0.137, Uvicorn, prometheus-fastapi-instrumentator.
- Datos: SQLAlchemy 2.0 async, asyncpg, pgvector, Redis 8, Neo4j 6, MinIO.
- IA/NLP: torch (CPU pin en base), sentence-transformers, docling, langchain, tiktoken.
- Resiliencia: tenacity, aiobreaker (circuit breaker), aio-pika.
- Todas las versiones están **pinneadas** (bien).

### Lo que ya está bien resuelto (no tocar)
- ✅ **Clean Architecture real** con puertos/interfaces por capa e inversión de dependencias.
- ✅ **DI container** (`configuration/dependencies.py`) con registro ordenado, *cleanup stack* y **rollback en reversa** si falla el arranque.
- ✅ **Invariantes de producción** (`production_invariants.py`): rechaza arrancar con `APP_RELOAD`, `LOG_LEVEL=DEBUG`, CORS `*`, secretos débiles, TLS desactivado en MinIO/RabbitMQ/Neo4j, Redis por defecto. Excelente.
- ✅ **Logging estructurado JSON** con `request_id`, `cause_chain`, contexto seguro y UTC.
- ✅ **Manejo de errores centralizado** (`exception_handlers.py`) con jerarquía `AppException`, mapeo de status, y propagación de `X-Request-ID`.
- ✅ **Health/Readiness** separados; `/ready` sondea Redis, DB, RabbitMQ y MinIO y devuelve 503 degradado.
- ✅ **Mensajería confiable**: patrón *outbox-lite* (Redis), DLQ/reintentos con `max_delivery_attempts`, límite de tamaño de mensaje, validación de envelope, y **propagación del bearer token del usuario** a través de la cola (con restauración para no filtrar entre mensajes).
- ✅ **Idempotencia**: locks en Redis (scripts Lua `release-if-owner`) en consumers de ingest/reembed/reprocess/graph.
- ✅ **SQL parametrizado**: las únicas interpolaciones por f-string son una cláusula constante y el vector de floats; **sin riesgo de inyección**.
- ✅ **AuthZ explícita** por endpoint (`Authorizer.require_permissions`) + middleware de autenticación con paths excluidos.
- ✅ **Rate limiting** distribuido por usuario/ruta con ventana deslizante en Redis (Lua atómico).
- ✅ **Dockerfile multi-stage**, usuario no-root, modelos pre-descargados en build, `HEALTHCHECK`.
- ✅ **Higiene de código**: 0 `TODO/FIXME`, 0 `print()`, 0 `except:` desnudos, 0 `eval/exec` de Python. ruff + mypy (estricto en `domain`/`application`) configurados.

---

## 2. FASE 1 — Auditoría: hallazgos

### 🟠 ALTOS

#### A1. Secretos y archivos `.env` versionados en git
- **Problema:** `env/.env`, `env/.env.docker`, `env/.env.docker.gpu` están **trackeados en git** y contienen credenciales (`DATABASE_MANAGER_PASSWORD=aura_password`, `MINIO_MANAGER_SECRET_KEY=aura_password`, `NEO4J_MANAGER_PASSWORD=aura_password`, `RABBITMQ_MANAGER_URL=amqp://aura_root:aura_password@...`). Aunque hoy son credenciales de desarrollo, **quedan en el historial de git**.
- **Impacto:** *secret sprawl*; si alguna vez se reutiliza un patrón/credencial real, queda expuesto permanentemente en la historia. Riesgo de filtración si el repo se vuelve público o se comparte.
- **Severidad:** Alto.
- **Propuesta:** (1) Crear `env/.env.example` con claves sin valores. (2) Dejar de trackear los `.env` reales (`git rm --cached`). (3) Rotar cualquier credencial que haya sido real. (4) En prod, inyectar desde un *secrets manager* (ya soportado: `pydantic-settings` lee de variables de entorno). *Mitigante existente:* `production_invariants` rechaza estos secretos débiles en producción y `.dockerignore` los excluye de la imagen.

#### A2. No existe `.gitignore`
- **Problema:** No hay archivo `.gitignore` en la raíz. Hoy el árbol está limpio (no hay `__pycache__`/`.idea`/`.pytest_cache` trackeados), pero nada lo impide.
- **Impacto:** alto riesgo de commitear basura, cachés de modelos, o secretos por accidente. Es la causa raíz que permite A1.
- **Severidad:** Alto.
- **Propuesta:** añadir `.gitignore` (puede derivarse del `.dockerignore` existente: `__pycache__/`, `*.py[cod]`, `.idea/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `env/.env`, `.env.*`, `*.log`, `.venv/`).

#### A3. Sin pipeline de CI/CD
- **Problema:** no hay `.github/workflows` ni equivalente. ruff, mypy y pytest están configurados pero **no se ejecutan automáticamente**.
- **Impacto:** las garantías de calidad dependen de la disciplina manual; regresiones de tipado/lint/tests pueden llegar a `main`.
- **Severidad:** Alto (de proceso).
- **Propuesta:** workflow que en cada PR corra `ruff check`, `mypy`, `pytest`, build de imagen Docker, y opcionalmente `pip-audit`/escaneo de secretos.

### 🟡 MEDIOS

#### M1. Cobertura de tests parcial y sin medición
- **Problema:** 19 archivos de test, mayormente a nivel **controller**. Servicios pesados (`document_ingestion_service` 556 LOC, `graph_query_service` 524, `create_document_service` 506) y repositorios (`fragment_repository` 792, `document_repository` 452) tienen poca o nula cobertura unitaria. No hay tests de integración del flujo de mensajería (outbox → publisher → consumer → idempotencia). `requirements.test.txt` no incluye `pytest-cov`.
- **Impacto:** la lógica de negocio más crítica y compleja es la menos cubierta; difícil refactorizar con seguridad.
- **Severidad:** Medio.
- **Propuesta:** añadir `pytest-cov` y un umbral mínimo; priorizar tests de ingestion/graph y un test de integración del ciclo de cola (con testcontainers o broker en memoria).

#### M2. Duplicación en gestión de dependencias (DRY)
- **Problema:** `requirements.gpu.txt` es una **copia completa** de `requirements.txt`; la única diferencia son 4 líneas (`--extra-index-url` y los `torch/torchaudio/torchvision` `+cpu` vs `+cu130`).
- **Impacto:** *drift* garantizado a futuro — al subir una versión en un archivo es fácil olvidar el otro.
- **Severidad:** Medio.
- **Propuesta:** dividir en `requirements/base.txt` (todo excepto torch) + `requirements/torch.cpu.txt` / `requirements/torch.gpu.txt`, e incluir base con `-r base.txt`. Mantiene un único punto de verdad.

#### M3. Observabilidad de negocio limitada
- **Problema:** solo existe **una** métrica custom (`structural_chunk_fallback_total`). El resto es instrumentación HTTP genérica. No hay métricas de negocio (documentos ingeridos, latencia de LLM, profundidad de cola, fallos por etapa) ni tracing distribuido (OpenTelemetry).
- **Impacto:** difícil diagnosticar cuellos de botella en el pipeline asíncrono y correlacionar entre servicios.
- **Severidad:** Medio.
- **Propuesta:** añadir contadores/histogramas por etapa del pipeline y por proveedor LLM; evaluar OpenTelemetry para trazas cross-service (ya se propaga `request_id`).

#### M4. README/documentación operativa inexistente (antes de este informe)
- **Problema:** el `README.md` estaba vacío. No había guía de setup, variables de entorno, arranque local, ni runbook.
- **Impacto:** onboarding lento; conocimiento operativo solo en la cabeza del autor.
- **Severidad:** Medio.
- **Propuesta:** documentar arranque (docker / local), tabla de variables de entorno (referenciar `env/.env.example`), diagrama del pipeline y runbook de incidentes. (La carpeta `docs/` ya tiene buen material de adapters/API que puede enlazarse.)

#### M5. Parámetros de rate limit y umbrales hardcodeados
- **Problema:** `_STRICT_RATE=20`, `_DEFAULT_RATE=60`, `_WINDOW_SECONDS=60` son constantes de módulo en `rate_limiter.py`. El rate limiter además **falla abierto** (si `redis_client is None`, no limita).
- **Impacto:** no se pueden ajustar límites por entorno sin redeploy; el *fail-open* puede ser deseado (disponibilidad) pero debe ser una decisión consciente.
- **Severidad:** Medio/Bajo.
- **Propuesta:** mover límites a settings por entorno; documentar explícitamente la política *fail-open*.

### 🟢 BAJOS / Observaciones

- **B1. Readiness no sondea Neo4j.** `/ready` no incluye Neo4j cuando el grafo está activo. Es coherente con el diseño (el módulo KG **degrada con gracia** si Neo4j no está al arrancar), pero un fallo de Neo4j en caliente no se reflejará en readiness. Documentar como decisión.
- **B2. `requirements.test.txt` mínimo.** Solo `pytest` + `pytest-asyncio`; los tests dependen implícitamente de las deps de la app. Añadir explícitamente lo necesario (`pytest-cov`, etc.).
- **B3. Boilerplate por endpoint.** Un controller-clase + interfaz + carpeta por endpoint multiplica archivos. Es una decisión arquitectónica consistente y defendible (aislamiento, testabilidad), pero aumenta la superficie de mantenimiento; tenerlo presente.
- **B4. Versiones "del futuro" pinneadas** (torch 2.11, fastapi 0.137, pydantic 2.13). Consistentes con el entorno; mantener `pip-audit` en CI para vigilar CVEs.
- **B5. `test_documents/` y PDFs versionados** (decretos, leyes, etc.) inflan el repo. Evaluar Git LFS o un bucket de fixtures.
- **B6. `_json_safe` del logger** hace `json.dumps` por cada campo de contexto para validar serializabilidad — costo menor por log; aceptable, pero a volumen alto considerar *fast path*.

---

## 3. FASE 2 — Plan de refactorización priorizado

> Ordenado por relación impacto/esfuerzo. Nada de esto se ejecutó (solo informe).

### Prioridad 0 — Higiene del repo (rápido, alto impacto)
| # | Qué | Por qué | Beneficio | Riesgo |
|---|-----|---------|-----------|--------|
| 1 | Añadir `.gitignore` (A2) | Evita commits accidentales | Protección permanente | Nulo |
| 2 | Dejar de trackear `.env` + crear `.env.example` + rotar (A1) | Eliminar secretos del control de versiones | Reduce superficie de filtración | Bajo (coordinar con despliegues) |
| 3 | Añadir CI (ruff/mypy/pytest/build) (A3) | Automatizar garantías ya configuradas | Frena regresiones | Nulo |

### Prioridad 1 — Confianza para evolucionar
| # | Qué | Por qué | Beneficio | Riesgo |
|---|-----|---------|-----------|--------|
| 4 | `pytest-cov` + tests de services/repos críticos (M1) | Cubrir la lógica más compleja | Refactors seguros | Esfuerzo medio |
| 5 | Test de integración del ciclo de cola (M1) | El flujo asíncrono es el corazón del sistema | Detecta regresiones de idempotencia/DLQ | Requiere infra de test |
| 6 | Refactor de `requirements` (M2) | Eliminar duplicación CPU/GPU | Sin drift de deps | Bajo |

### Prioridad 2 — Operación en producción
| # | Qué | Por qué | Beneficio | Riesgo |
|---|-----|---------|-----------|--------|
| 7 | Métricas de negocio + (opcional) OpenTelemetry (M3) | Diagnóstico del pipeline | Observabilidad real | Bajo/Medio |
| 8 | Límites de rate configurables por entorno (M5) | Ajuste sin redeploy | Flexibilidad operativa | Nulo |
| 9 | Runbook + tabla de envs en docs (M4) | Onboarding y on-call | Menor MTTR | Nulo |

### Categorías (referencia rápida)
- **Arquitectura:** ya sólida; no requiere cambios estructurales. Solo reducir boilerplate si se vuelve un problema (B3).
- **Seguridad:** A1, A2 (acción inmediata); validaciones de entrada ya presentes.
- **Base de Datos:** consultas parametrizadas y eficientes (window functions, `load_only`, `defer`, chunked IDs); recordar que el DDL se gestiona externamente (sin migraciones — ver nota de memoria del proyecto). Considerar herramienta de migraciones a futuro.
- **API:** controllers delgados y consistentes; OK.
- **Testing:** M1 (foco principal).
- **Logging:** estructurado y correcto; OK.
- **Configuración:** centralizada en `pydantic-settings` con invariantes; A1/M5 pendientes.
- **Docker:** multi-stage, no-root, healthcheck; añadir `.dockerignore` ya existe. OK.
- **Performance:** sin problemas evidentes; vigilar carga de modelos en arranque (ya hay warmup en hilos).
- **Mantenibilidad:** alta; M2/M4 la mejoran.
- **Observabilidad:** M3.

---

## 4. FASE 3–5 — Estado y recomendaciones

> **No se ejecutó refactorización** (instrucción explícita: *"no me cambies nada"*). Esta sección documenta qué haría cada fase y el estado actual frente a "producción".

### Checklist de Producción (Fase 4)
| Capacidad | Estado | Nota |
|-----------|:---:|------|
| Configuración segura | 🟡 | Invariantes ✅, pero secretos en git (A1) |
| Liveness / Readiness | ✅ | `/api/v1/health`, `/api/v1/ready` (Neo4j no sondeado, B1) |
| Logging estructurado | ✅ | JSON + request_id + cause_chain |
| Métricas | 🟡 | HTTP ✅, negocio mínimo (M3) |
| Trazabilidad | 🟡 | request_id propagado; sin tracing distribuido |
| Manejo de errores | ✅ | Centralizado, jerarquía `AppException` |
| Validación robusta | ✅ | Pydantic + sanitización BM25 + límites de dominio |
| Docker optimizado | ✅ | Multi-stage, no-root, healthcheck |
| Gestión de secretos | 🟡 | Mecanismo OK (env vars); falta sacarlos de git |
| Mensajería confiable | ✅ | Outbox-lite, DLQ, idempotencia |
| Apagado ordenado | ✅ | `shutdown_dependencies` en reversa |
| CI/CD | 🔴 | Inexistente (A3) |

### Deuda técnica restante (resumen)
1. Secretos en historial de git (A1).
2. Ausencia de `.gitignore` y de CI (A2, A3).
3. Brechas de cobertura en services/repos y flujo de cola (M1).
4. Duplicación CPU/GPU en requirements (M2).
5. Observabilidad de negocio y tracing (M3).
6. Documentación operativa/runbook (M4, parcialmente cubierto por este informe).
7. Sin herramienta de migraciones de BD (DDL externo) — gestionar ALTERs a mano es frágil a largo plazo.

### Próximos pasos recomendados (orden sugerido)
1. **Hoy:** `.gitignore` + sacar `.env` de git + `.env.example` (P0-1, P0-2).
2. **Esta semana:** CI con ruff/mypy/pytest/build + `pip-audit` (P0-3).
3. **Próximo sprint:** `pytest-cov` y tests de `document_ingestion_service`, `graph_query_service`, repositorios y ciclo de cola (P1-4, P1-5).
4. **Después:** refactor de requirements (P1-6), métricas de negocio (P2-7), límites configurables (P2-8), runbook (P2-9).
5. **Backlog:** evaluar migraciones de BD, Git LFS para fixtures, y reducción de boilerplate si crece el número de endpoints.

---

*Fin del reporte. No se realizaron cambios en el código fuente; el único archivo escrito es este `README.md`.*
