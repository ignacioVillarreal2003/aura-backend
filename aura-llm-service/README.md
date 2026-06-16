# AURA LLM Service — Informe de Auditoría y Plan de Producción

> Backend de servicios LLM (FastAPI + LangGraph + Ollama) para la plataforma AURA.
> Este documento es el **informe de auditoría** (no se han realizado cambios de código).
> Fecha: 2026-06-15 · Alcance: 324 módulos Python (~19.5K LOC).

---

## 0. Resumen ejecutivo

**Este no es un proyecto greenfield desordenado.** Es un servicio con Clean Architecture ya
aplicada y un nivel de madurez de producción **alto**: DI con rollback, logging estructurado,
circuit breaker por host, retries, rate-limiting atómico, métricas Prometheus, tracing OTel,
guardrails de entrada/salida, healthchecks, Docker no-root y build reproducible desde lock.

El trabajo pendiente para "listo para producción" es **acotado**: no requiere reescritura, sino
cerrar huecos puntuales de seguridad operativa, consistencia y verificación. La auditoría se
calibra en consecuencia.

> ⚠️ **Estado del repositorio al momento de auditar:** hay un **refactor grande sin commitear**
> (decenas de archivos `D`/`R` en `git status`). Se verificó estáticamente que **no quedaron
> imports colgando** a los módulos borrados y que las rutas renombradas a `interfaces/` +
> `exceptions/` son consistentes. **No fue posible ejecutar la test suite** en el entorno de
> auditoría (sin venv; `uvicorn` y dependencias no instaladas).

---

## 1. Lo que ya está bien hecho (verificado en código)

| Eje | Estado | Evidencia |
|---|---|---|
| Arquitectura | ✅ Limpia y por capas | `api/ application/ domain/ infrastructure/ configuration/`; interfaces ABC; DI vía `app.state` |
| DI / ciclo de vida | ✅ Registry con rollback en orden inverso ante fallo de startup | `app/configuration/dependencies.py:48-171` |
| Logging | ✅ JSON estructurado, UTC, propagación de `request_id` | `app/configuration/logging_configuration.py`, `app/api/handlers/exception_handlers.py` |
| Manejo de errores | ✅ Estrategia única `AppException` + 4 handlers consistentes; 500 con mensaje genérico (sin fuga interna) | `app/api/handlers/exception_handlers.py`, `app/application/exceptions/app_exception.py` |
| Resiliencia | ✅ Circuit breaker **por host**, retries `tenacity`, fail-open | `app/infrastructure/http/http_client/http_client.py:74-90,221-240` |
| Rate limiting | ✅ Sliding window **atómico en Lua**, header `Retry-After`, fail-open | `app/api/dependencies/rate_limiter.py:17-82` |
| Observabilidad | ✅ Prometheus + OTel/Phoenix + propagación W3C trace-context | `app/main.py:77-90`, `http_client.py:32-42` |
| Seguridad base | ✅ Sin secretos hardcodeados; Redis URL como `SecretStr`; body-size limit; auth middleware; guardrails in/out | greps limpios; `app/infrastructure/persistence/.../redis_client.py:28-31` |
| Health | ✅ `/health` (liveness) + `/ready` (readiness con checks de http_client, ollama, redis) | `app/api/controllers/health_controller/health_controller.py` |
| Docker | ✅ `python:3.13-slim`, usuario no-root, healthcheck, build desde `requirements.lock.txt` | `Dockerfile` |
| Configuración | ✅ `pydantic-settings` con validadores (`log_level`, `cors_origins`) | `app/configuration/environment_variables.py` |

**Verificado y NO encontrado:** secretos hardcodeados, `print()`, `except: pass`, bare-excepts,
`TODO/FIXME`, imports colgando a módulos borrados.

---

## 2. Hallazgos

Severidad: **Crítico** / **Alto** / **Medio** / **Bajo**.

### #1 — No hay forma de validar el working tree (Alto · proceso)
- **Problema:** refactor masivo sin commitear y test suite no ejecutable en el entorno de auditoría.
- **Impacto:** sin red de seguridad; no se puede confirmar que el árbol actual arranca y pasa tests.
- **Solución:** crear venv, instalar `requirements.txt` + `requirements/requirements-dev.txt`,
  correr `ruff check .` y `pytest --cov` hasta baseline verde **antes** de cualquier refactor.

### #2 — Archivos `.env*` versionados en HEAD (Medio · seguridad)
- **Problema:** `.env`, `.env.docker`, `.env.docker.gpu` están trackeados en HEAD (el refactor en
  curso los borra ✅, moviéndolos a `env/` ya ignorado). El **historial git los retiene**.
- **Impacto:** los valores actuales son de desarrollo (localhost, sin secretos reales observados),
  pero el patrón es peligroso si alguna vez llevaron credenciales reales.
- **Solución:** (a) confirmar que en el historial nunca se comiteó un secreto real; (b) agregar
  un `.env.example` versionado (hoy **no existe**); (c) secretos siempre vía gestor de secretos /
  variables de entorno del orquestador.

### #3 — `request.client.host` sin trusted-proxy (Medio · seguridad/correctitud)
- **Problema:** la identidad del rate-limit y el client-IP de logs usan `request.client.host`
  directamente, sin manejo de proxy confiable (`X-Forwarded-For`).
- **Impacto:** detrás de un LB/ingress, todo el tráfico se atribuye a la IP del proxy → rate-limit
  y trazabilidad por IP incorrectos.
- **Solución:** `ProxyHeadersMiddleware` / `--forwarded-allow-ips` con lista de proxies confiables;
  derivar la IP real de `X-Forwarded-For`. Ref: `app/api/dependencies/rate_limiter.py:42-48`.

### #4 — Migración incompleta a `interfaces/` + `exceptions/` (Medio · mantenibilidad)
- **Problema:** el refactor movió 6 servicios (`checklist`, `decision_brief`, `lessons_learned`,
  `quiz`, `report`, `timeline`) a subpaquetes `interfaces/` + `exceptions/`, pero
  **`general_chat_service` quedó en el layout plano** (único outlier).
- **Impacto:** inconsistencia estructural; fricción de mantenimiento y de convención.
- **Solución:** migrar `general_chat_service` a la misma convención y actualizar sus importadores
  (`general_chat_controller.py:13`, `general_chat_service.py:14,17`).

### #5 — Swagger/OpenAPI siempre expuesto (Medio · seguridad)
- **Problema:** `/api/docs`, `/api/redoc`, `/api/openapi.json` se exponen sin gate por entorno.
- **Impacto:** superficie de información (esquema de API) en producción.
- **Solución:** desactivar o proteger los docs cuando `environment_variables.is_production()`.
  Ref: `app/main.py:65-67`.

### #6 — Cobertura de tests desconocida (Medio · testing)
- **Problema:** 38 archivos de test para 324 módulos; `pytest-cov` disponible pero sin umbral.
- **Impacto:** riesgo no cuantificado para un sistema "a producción mañana".
- **Solución:** medir con `pytest --cov`, fijar umbral mínimo en CI, priorizar caminos críticos
  (handlers de error, rate-limit, circuit breaker del `http_client`, startup/rollback de DI).

### #7 — README vacío (Medio · mantenibilidad)
- **Problema:** `README.md` estaba vacío (0 líneas).
- **Impacto:** sin documentación de arranque, configuración u operación.
- **Solución:** documentar ejecución, variables de entorno, endpoints y runbook operativo
  (este informe es el primer paso; ver §5).

### #8 — Efectos colaterales de import (Bajo · testabilidad)
- **Problema:** `environment_variables` se instancia y **loguea al importar el módulo**
  (`environment_variables.py:83-86`); `rate_limiter` fija los límites a globals de módulo en import
  (`rate_limiter.py:13-15`).
- **Impacto:** dificulta tests con configuración alternativa y recarga de settings.
- **Solución:** `@lru_cache def get_settings()`; leer límites por-request o vía settings inyectados.

### #9 — `requirements.txt` con pisos `>=` (Bajo · build)
- **Problema:** dev instala con pisos `>=` (no reproducible); solo Docker usa `requirements.lock.txt`.
- **Impacto:** drift potencial entre entornos de dev y la imagen de prod.
- **Solución:** lock también para dev, o adoptar `pip-tools` / `uv` para resolución determinista.

### #10 — Readiness acoplado a `ollama.is_healthy()` (Bajo · operación)
- **Problema:** el probe de readiness depende de `ollama_facade.is_healthy()`.
- **Impacto:** si ese check no es local/barato/no-bloqueante, el probe puede aletear y sacar el pod
  de rotación bajo carga del LLM.
- **Solución:** confirmar que el check es local y rápido; aplicar timeout por dependencia y
  considerar separar "deep health" de "readiness".

---

## 3. Plan de refactorización priorizado

> Pendiente de ejecución. **P0 es bloqueante** del resto.

**P0 — Estabilizar la base (antes de tocar código)**
- venv + `requirements.txt` + `requirements-dev.txt`; `ruff check .` y `pytest --cov` → baseline verde.
- *Beneficio:* red de seguridad. *Riesgo:* puede revelar que el refactor en curso rompió algo
  (mejor descubrirlo antes de seguir).

| Categoría | Cambios | Hallazgos |
|---|---|---|
| **Seguridad** | `.env.example` + auditar historial · trusted-proxy · gate de docs en prod | #2, #3, #5 |
| **Mantenibilidad** | Terminar migración `general_chat_service` · README/runbook · settings sin side-effects de import | #4, #7, #8 |
| **Testing** | Medir cobertura, fijar umbral en CI, cubrir caminos críticos | #6 |
| **Config / Build** | Lock para dev (`pip-tools`/`uv`) | #9 |
| **Operación** | Validar coste/latencia de checks de readiness; timeouts por dependencia | #10 |
| **Arquitectura / Observabilidad / Performance / DB** | Sin hallazgos accionables nuevos — ya cubiertos | — |

Para cada cambio, antes de ejecutarlo se documentará: **qué** se hace, **por qué**, **beneficio
esperado** y **riesgo**, respetando: no romper funcionalidad, compatibilidad hacia atrás y
verificar (tests verdes) antes de borrar.

---

## 4. Riesgos y decisiones abiertas

- **Refactor en curso sin commitear:** decidir si se commitea/cierra primero para arrancar limpio,
  o si se continúa sobre el working tree actual. Recomendado: cerrar el refactor con tests verdes
  antes de iniciar la Fase 3.
- **Entorno de auditoría sin deps:** todas las validaciones dinámicas (tests, lint, arranque)
  quedan pendientes de un entorno con venv.

---

## 5. Cómo ejecutar (borrador — completar tras validar)

```bash
# 1) Entorno
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements/requirements-dev.txt

# 2) Configuración (crear env/.env a partir de un .env.example aún por crear)
#    Variables clave: CORS_ORIGINS, ENVIRONMENT, OLLAMA_LLM_FACADE_*, REDIS_*, DOCUMENT_CONTEXT_PROVIDER_*

# 3) Calidad
ruff check .
pytest --cov

# 4) Desarrollo
uvicorn app.main:app --reload --port 8001

# 5) Docker
docker build -t aura-llm-service .
docker run -p 8000:8000 --env-file env/.env aura-llm-service
```

Endpoints de salud: `GET /api/v1/health` (liveness) · `GET /api/v1/ready` (readiness) ·
`GET /metrics` (Prometheus) · Docs: `/api/docs`, `/api/redoc`.

---

## 6. Próximos pasos recomendados

1. **(P0)** Levantar venv y dejar `pytest` + `ruff` en verde sobre el working tree actual.
2. Decidir el destino del refactor en curso (commitear vs. continuar).
3. Ejecutar quick-wins de bajo riesgo: `.env.example`, migración `general_chat_service`, gate de
   docs en prod, settings sin side-effects de import.
4. Endurecer seguridad operativa: trusted-proxy para rate-limit/logs.
5. Medir cobertura y fijar umbral en CI.
6. Completar este README con runbook operativo (escalado, troubleshooting, dashboards de métricas).
