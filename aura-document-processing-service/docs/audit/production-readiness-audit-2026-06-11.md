# Auditoría de preparación para producción — aura-document-processing-service

Fecha: 2026-06-11
Alcance: repositorio completo del microservicio (app/, requirements/, Docker, tests, docs, env).

## Resumen ejecutivo

El servicio ya tiene una base sólida de nivel producción: arquitectura por capas con interfaces
(controllers → services → repositories), settings tipados por componente con `SecretStr` y
validadores, logging JSON estructurado con request-id, métricas Prometheus, circuit breakers y
reintentos en HTTP/MinIO/RabbitMQ/BD, outbox-lite con reconciliación, DLQ con límite de
reintentos, validación profunda de uploads (magic numbers, tamaño, filename), Cypher y SQL
parametrizados, soft-deletes y rollback ordenado del startup.

La auditoría encontró **2 problemas críticos**, **3 altos**, **8 medios** y varios menores.
La suite de tests (137 tests) tenía **13 fallos** que se reducen a 3 causas raíz (hallazgos C1,
C2 y A1).

## Hallazgos

### Críticos

**C1 — Contrato de autenticación service-to-service desactualizado**
- Archivo: `app/infrastructure/http/authentication_provider/authentication_provider.py`
- Problema: con `X-Service-Api-Key` válida, `evaluate_service_auth` devolvía un usuario fijo
  `id=0` sin roles ni permisos e ignoraba los headers `X-User-Id`, `X-User-Email`,
  `X-User-Roles`, `X-User-Permissions`. El contrato AURA (implementado en el resto de
  servicios y asumido por los tests) exige propagar la identidad del usuario por headers y
  responder 400 si faltan.
- Impacto: cualquier llamada service-to-service fallaba la autorización por permisos
  (usuario sin permisos) o, peor, operaba con una identidad ficticia `0` que no existe.
  3 tests fallaban.
- Solución: construir el `AuthenticatedUser` desde los headers; 400 si falta o es inválido
  `X-User-Id`/`X-User-Email`.

**C2 — `/api/v1/ready` exigía autenticación**
- Archivo: `app/configuration/middlewares/authentication_middleware.py`
- Problema: la lista de rutas excluidas incluía `/api/v1/health` pero no `/api/v1/ready`.
- Impacto: las readiness probes de Kubernetes/compose reciben 401 → el servicio nunca se
  marca Ready en producción. 2 tests fallaban.
- Solución: excluir `/api/v1/ready` de la autenticación.

### Altos

**A1 — Handler de errores de validación devolvía 500 en vez de 422**
- Archivo: `app/api/handlers/exception_handlers.py`
- Problema: `request_validation_exception_handler` pasaba `exc.errors()` crudo a
  `JSONResponse`. En pydantic v2, cuando un `field_validator`/`model_validator` lanza
  `ValueError`, `errors()` incluye `ctx: {"error": ValueError(...)}`, que no es serializable
  a JSON → `TypeError` → 500.
- Impacto: toda petición rechazada por validadores custom (ids duplicados, ids fuera de
  rango, source==target en paths de grafo…) devolvía 500 InternalServerError en vez de 422
  con el detalle. 8 tests fallaban.
- Solución: serializar con `fastapi.encoders.jsonable_encoder`.

**A2 — `SERVICE_API_KEY` con default conocido y sin guard de producción**
- Archivo: `app/configuration/environment_variables.py` (+ `.env*`)
- Problema: default `"service_api_key"`; sin warning ni fail-fast. `is_production()` era una
  heurística (no reload y no DEBUG) que ignoraba la variable `ENVIRONMENT`.
- Impacto: si en producción no se configura la clave, cualquier caller que conozca el default
  se autentica como servicio.
- Solución: `is_production()` honra `ENVIRONMENT`; fail-fast si la clave es el default en
  producción y warning en cualquier otro entorno.

**A3 — Contenedores ejecutan como root**
- Archivos: `Dockerfile`, `DockerfileGPU`
- Problema: sin directiva `USER`; caches de modelos bajo `/root/.cache`.
- Impacto: superficie de escalada innecesaria si se compromete el proceso.
- Solución: usuario no privilegiado, caches en ruta legible por ese usuario (`/opt/cache`).

### Medios

**M1 — BM25 interpola texto saneado en el SQL (f-string)**
- `fragment_repository.get_most_relevant_fragments_bm25` construía `content @@@ '{texto}'`.
  Mitigado por el allowlist regex (las comillas se eliminan), pero frágil ante cambios del
  sanitizador. Solución: bind parameters para query, min_score y limit.

**M2 — `NotificationClient` crea un `httpx.AsyncClient` por evento**
- Handshake TCP/TLS por notificación y sin pool. Solución: cliente persistente lazy con
  `aclose()` en el shutdown.

**M3 — Exclusiones de autenticación obsoletas**
- `/api/v1/create-document/internal` y `/api/health` no existen como rutas. Si alguien
  (re)añade esa ruta, quedaría pública sin querer. Solución: eliminar entradas muertas.

**M4 — Header `Idempotency-Key` aceptado pero nunca consumido**
- `optional_idempotency_key` guarda el valor en `request.state` y ningún código lo lee.
  API engañosa: el caller cree que hay idempotencia. Documentado como deuda; implementar
  dedupe en Redis o eliminar el parámetro.

**M5 — `requirements.txt` y `requirements.gpu.txt` en UTF-16**
- pip los tolera (auto-detección de BOM) pero otras herramientas (dependabot, renovate,
  pip-tools, audits) fallan. Además `redis>=5.0.0` estaba duplicado. Solución: reescribir
  en UTF-8 y dedupe.

**M6 — Rate limiter fail-open con límites hardcodeados**
- `_STRICT_RATE=20`, `_DEFAULT_RATE=60` no configurables por entorno; dos pipelines no
  atómicos permiten sobre-admisión bajo concurrencia; si Redis no está, no limita (decisión
  consciente de disponibilidad). Deuda aceptable; documentada.

**M7 — Alembic declarado sin migraciones en el repo**
- El esquema se gestiona fuera del servicio (no hay `alembic/`). `pycryptodome` no tiene
  usos visibles. Revisar y limpiar dependencias en una iteración de plataforma.

**M8 — Acoplamiento con tablas de otros dominios**
- ORM de `chat` y `document_collection` viven aquí para joins de autorización. Aceptado por
  pragmatismo (BD compartida), pero documentado como riesgo de evolución de esquema.

### Bajos

- B1: `_parse_comma_list` era código muerto (pasa a usarse con C1).
- B2: naming inconsistente `download_document_controller_interface.py` (patrón invertido);
  `graph_ontology_controller` sin archivo de interfaz.
- B3: imagen sin `HEALTHCHECK` (aceptable si el orquestador define probes; añadido en compose/k8s).
- B4: `CORS_ORIGINS=["*"]` en `.env` local (en `.env.docker` ya hay lista explícita);
  `allow_credentials` se desactiva correctamente con wildcard.
- B5: suite de tests requiere stack completo instalado; con instalación ligera corre en <2s.

## Plan de refactorización (Fase 2)

Prioridad 1 (bugs con tests rojos — sin riesgo de regresión, los tests definen el contrato):
1. C1 contrato service-auth (Seguridad/API).
2. C2 excluir `/api/v1/ready` (Configuración/Observabilidad).
3. A1 `jsonable_encoder` en el handler de validación (API/Errores).

Prioridad 2 (hardening sin cambio funcional):
4. A2 guard de `SERVICE_API_KEY` + `is_production()` por `ENVIRONMENT` (Seguridad/Config).
5. M3 limpiar exclusiones muertas (Seguridad).
6. M1 bind params en BM25 (Base de datos/Seguridad).
7. M2 cliente persistente en `NotificationClient` (Performance).
8. M5 requirements UTF-8 + dedupe (Mantenibilidad).
9. A3 usuario no root en Dockerfiles (Docker/Seguridad).

Riesgos: C1 endurece la entrada service-to-service (callers sin headers de identidad pasarán
de 200 a 400) — alineado con el contrato del resto de servicios AURA; A2 hace fail-fast en
producción si la clave es el default — comportamiento deseado; el resto es neutral.

Deuda explícitamente NO abordada en esta pasada (ver M4, M6, M7, M8, B2): requiere decisión
de producto/plataforma o cambios cross-servicio.
