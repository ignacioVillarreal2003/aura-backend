 AUDITORÍA TÉCNICA — aura-document-processing-service

  Modo: solo lectura · Alcance: repositorio completo (362 archivos versionados, ~26.437 LOC Python) · Fecha: 2026-06-14
  Metodología: inspección directa de código y configuración. Toda conclusión se basa en evidencia citada (archivo:línea). Donde falta contexto verificable, se indica
  explícitamente.

  ▎ Nota de honestidad metodológica: revisé en profundidad las capas de configuración, seguridad, persistencia (SQL + Cypher), almacenamiento, mensajería,
  ▎ autenticación/autorización, controladores representativos y el flujo de ingesta. No abrí exhaustivamente los ~80 archivos de procesadores (readers/embedders/splitters) ni cada
  ▎ servicio de grafo; las conclusiones sobre esos módulos se marcan como “no verificado en detalle”.

  ---
  FASE 1 — INVENTARIO Y ARQUITECTURA

  1.1 Estructura (resumen)

  app/
  ├── api/              # Capa de entrada: controllers (1 carpeta/endpoint + interface), schemas, handlers, dependencies, openapi
  ├── application/      # Casos de uso: services/, processors/ (readers, embedders, splitters, rerankers, cleaners), authorization/
  ├── domain/           # DTOs, constants, field_limits, types, authenticated_user  (núcleo sin dependencias de framework)
  └── infrastructure/   # http/ (providers + http_client), messaging/rabbitmq (consumers, publishers, outbox), persistence/ (database, graph/neo4j, memory_database/redis,
  storages/minio)

  Soporte: test/ (15 archivos), docs/, http/ (REST client), scripts/download_models.py, requirements/, Dockerfile/DockerfileGPU, test_documents/ (PDFs/DOCX binarios versionados).

  1.2 Arquitectura

  - Estilo: Arquitectura limpia / hexagonal por capas (api → application → domain ← infrastructure), con interfaces explícitas por componente e inyección de dependencias vía
  app.state resuelta en dependencies.py.
  - Patrones: Repository, Factory (*_factory.py), Provider/Adapter (HTTP, storage), Transactional Outbox “lite” sobre Redis (redis_outbox_lite.py) con worker de reconciliación,
  Circuit Breaker (aiobreaker) + retries (tenacity), DLQ por reintentos en consumidores.
  - Flujo de datos (ingesta): POST /document → validación/upload a MinIO + fila en Postgres (status=uploaded) → publica DocumentIngestionCommand (vía outbox) →
  DocumentIngestionConsumer lee, descarga, parsea, limpia, fragmenta, embebe → persiste fragmentos → publica enrichment/graph-extraction. Reconciliación de documentos “colgados”
  vía get_stale_uploaded_documents + OutboxLiteWorker.
  - Cohesión: alta a nivel módulo. Acoplamiento: bajo entre capas; el punto de acoplamiento fuerte es dependencies.py (orquestador único, ~390 líneas). No detecté dependencias
  circulares de import.

  1.3 Dependencias (evaluación)

  ┌─────────────────────────────────────────────────────┬────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────┐
  │                     Dependencia                     │               Propósito                │                                Observación                                │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ fastapi/uvicorn/pydantic(-settings)                 │ Web + settings                         │ Uso correcto y central                                                    │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ sqlalchemy[async]/asyncpg/pgvector                  │ Persistencia + vectores                │ Correcto; ver hallazgos de índices                                        │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ neo4j                                               │ Grafo de conocimiento                  │ Bien encapsulado; opcional vía flag                                       │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ redis                                               │ Cache token, rate-limit, outbox, locks │ Uso intensivo y correcto                                                  │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ aio-pika                                            │ RabbitMQ                               │ Consumers con DLQ                                                         │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ torch(+cpu)/sentence-transformers/docling/tesseract │ ML/lectura                             │ Pesadas; horneadas en imagen                                              │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ httpx + aiobreaker + tenacity                       │ HTTP saliente resiliente               │ Buen patrón                                                               │
  ├─────────────────────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Todas (salvo torch)                                 │ —                                      │ Sin pin exacto (>=) ni lockfile/hashes → builds no reproducibles (ver C2) │
  └─────────────────────────────────────────────────────┴────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────┘

  ---
  FASE 2 — AUDITORÍA TÉCNICA (hallazgos por dominio)

  Seguridad — aspectos POSITIVOS (verificados)

  - SQL parametrizado vía ORM en todo document_repository.py (sin concatenación). Igual para Cypher: parámetros $x en todos los repos de grafo; la única interpolación de string es
  depth y está forzada a int y acotada (graph_relation_repository.py:196-197).
  - Validación de upload robusta: path traversal (..,/,\, null bytes), longitud, content-type permitido, magic numbers, y doble verificación de tamaño antes/después de stream
  (create_document_service.py:257-307).
  - Autorización fail-closed: ante error/JSON inválido/timeout, chat_membership_provider y document_collection_catalog_client devuelven “sin acceso” (:89-100, :102-113) — diseño
  correcto.
  - Manejo de errores sin fuga: handlers devuelven mensajes genéricos; stacktraces y cause_chain van solo a logs (exception_handlers.py).
  - Token de auth cacheado por hash SHA-256, no en claro como clave (authentication_provider.py:38-39); longitud máxima de bearer validada.

  Seguridad — HALLAZGOS

  - S1 [ALTO] — .env con credenciales versionado en git. .env, .env.docker, .env.docker.gpu están en git ls-files y .gitignore no excluye .env (.gitignore:1-52). El archivo
  contiene DATABASE_MANAGER_PASSWORD=aura_password, MINIO_MANAGER_SECRET_KEY=aura_password, RABBITMQ_..._password, NEO4J_MANAGER_PASSWORD=aura_password (.env:67-108). Aunque son
  defaults de desarrollo, (a) son secretos en el control de versiones y (b) se reutiliza la misma password en todos los servicios. Riesgo de que el patrón se arrastre a producción.
  - S2 [ALTO] — Bearer token del usuario propagado y persistido fuera de la request. El token se inyecta en DocumentIngestionCommand.auth_token (create_document_service.py:188),
  viaja por RabbitMQ y, si falla la publicación, se persiste en Redis en claro dentro del outbox (redis_outbox_lite.py:96-114). El consumidor lo re-establece para actuar como el
  usuario (base_consumer.py:122-126). Implica token en tránsito por el broker y token at-rest en Redis durante el TTL del outbox. Si los tokens son de larga duración, amplía la
  ventana de robo/replay.
  - S3 [MEDIO] — /metrics sin autenticación. Está en _EXCLUDED_PATHS del middleware (authentication_middleware.py:14) y expuesto por el instrumentator. Exposición de métricas
  internas (latencias, rutas, conteos) a cualquiera con acceso de red.
  - S4 [MEDIO] — Rate limiting fail-open. Si redis_client no está en app.state, _check_rate_limit retorna sin aplicar límite (rate_limiter.py:42-44). Una caída de Redis desactiva
  silenciosamente la protección. Además, para usuarios sin identidad cae a request.client.host (:46-51): tras un proxy/ingress todos comparten IP, colapsando el límite.
  - S5 [BAJO] — CORS por defecto ["*"] en .env:7 y default del settings (environment_variables.py:25). Mitigado porque configure_cors desactiva allow_credentials cuando hay *
  (cors_configuration.py:9), pero requiere disciplina en prod.
  - S6 [BAJO] — X-Request-ID aceptado del cliente sin límite de longitud y reflejado en cabecera de respuesta y logs (logging_middleware.py:21-29). Riesgo bajo de
  log-bloat/inyección (Starlette mitiga saltos de línea).

  Arquitectura — HALLAZGOS

  - A1 [ALTO] — Base de datos compartida / FK cross-service. El ORM declara Document.chat_id → ForeignKey("chat.id") (orm/document.py:14-21) y Fragment.document_id → document.id,
  pero la tabla chat no existe en este servicio. Igual, created_by/deleted_by son ids de usuario de otro servicio. Esto implica una BD compartida con FKs entre dominios, violando
  database-per-service y creando acoplamiento de datos y de despliegue (migraciones coordinadas).
  - A2 [MEDIO] — No hay gestión de migraciones. No existe Alembic ni carpeta de migraciones (git ls-files no devuelve nada). El esquema vive parcialmente como ORM, pero su
  creación/evolución no está versionada en este repo → riesgo de schema drift y de que los índices necesarios no existan (ver D1/D2).
  - A3 [MEDIO] — Idempotencia muerta/incompleta. optional_idempotency_key solo aparece en su propio archivo y en docs (grep), no está cableada en ningún controlador. La creación de
  documentos no deduplica, por lo que un reintento del cliente (o del navegador) puede crear documentos duplicados. La función promete una garantía que el sistema no cumple.
  - A4 [BAJO] — startup_dependencies monolítico (~390 líneas, dependencies.py:184-424): difícil de testear unitariamente y de razonar; concentra todo el grafo de objetos.

  Base de datos / Performance — HALLAZGOS

  - D1 [ALTO] — Ausencia de índices secundarios en columnas de filtrado frecuente (según el esquema en código). Todas las consultas filtran Document.deleted_at y ordenan por
  created_at; se filtra por chat_id, status y se unen fragmentos por Fragment.document_id — ninguna tiene índice declarado (orm/document.py, orm/fragment.py). Caveat: al no haber
  migraciones, no puedo verificar si existen índices en la BD real; debe confirmarse.
  - D2 [ALTO] — Sin índice ANN para el vector de embeddings. Fragment.vector = VECTOR(dim=…) no declara índice HNSW/IVFFlat (orm/fragment.py:32). Sin un índice ANN en pgvector, la
  búsqueda por similitud degrada a KNN exacto (scan completo), inaceptable para un servicio RAG a escala. Confirmar en la BD/migración externa.
  - D3 [BAJO] — index=True en la PK (document.py:12, fragment.py:20) es redundante: la clave primaria ya está indexada.

  API / Contratos

  - Endpoints REST consistentes y versionados (/api/v1), operation_id por ruta, responses OpenAPI por código, separación controller/interface. Validación vía Pydantic en
  formularios (create_document_form.py).
  - Endpoint admin (/admin/document/{id}/download) correctamente protegido por permiso DOWNLOAD_DOCUMENT_ADMIN y separado de la ruta de usuario
  (document_download_controller.py:49-73). Bien.

  Observabilidad — HALLAZGOS

  - POSITIVO: logging estructurado con extra, request_id propagado a respuestas y handlers, URLs/credenciales redactadas (url_safe, uri_safe, endpoint_safe), logging de claves de
  objeto solo por sufijo, readiness con sondas reales de Redis/DB/RabbitMQ/MinIO (health_controller.py:50-65).
  - O1 [MEDIO] — Sin tracing distribuido. No hay OpenTelemetry; request_id no se propaga a llamadas HTTP downstream ni a mensajes (los comandos llevan message_id, no contexto de
  traza) → correlación end-to-end limitada en un sistema multi-servicio asíncrono.
  - O2 [BAJO] — Sin métricas de negocio (documentos ingeridos/fallidos, profundidad de cola, fallos de extracción de grafo); solo métricas HTTP genéricas del instrumentator.

  Testing — HALLAZGOS

  - T1 [ALTO] — Cobertura muy baja. 15 archivos / 1.150 LOC de test vs ~26.437 LOC de app (~4%). Los tests cubren controladores, autenticación, authorizer, chat-membership y un
  repo de stats. No hay tests de los servicios núcleo (create/ingestion/enrichment/extraction/search/query), repositorios (document/fragment/grafo), procesadores, http_client,
  minio_manager, database_manager, outbox ni consumidores.
  - T2 [MEDIO] — Sin CI/CD en el repo. No hay .github/, GitLab CI, etc. Los quality gates (ruff/mypy/pytest están definidos en pyproject.toml) no se ejecutan automáticamente;
  dependen de disciplina local.

  Calidad de código

  - POSITIVO: estilo consistente, type hints amplios, jerarquías de excepciones por módulo, sin print()/breakpoint(), solo 4 TODO/FIXME, ejecución como usuario no-root en Docker,
  HEALTHCHECK, base slim, sin secretos en la imagen.
  - C1 [BAJO] — DRY: _normalize_bearer y _build_request_headers están duplicados literalmente en chat_membership_provider.py y document_collection_catalog_client.py.
  - C2 [BAJO] — Dependencias sin fijar + sin lockfile/hashes (requirements.txt, Dockerfile:22 pip install --upgrade) → builds no reproducibles y riesgo de cadena de suministro.
  - C3 [BAJO] — Inconsistencia de autorización: document_download_service consulta el catálogo con authorization_header=None (usa token de servicio/fallback) (:166-178), mientras
  graph_query_service propaga el header del usuario. Comportamiento divergente, confuso y no documentado.

  ---
  FASE 3 — MATRIZ DE HALLAZGOS

  ┌─────┬────────────────┬───────────────────────┬──────────────────────────────────────────────────┬───────────────────────────┬──────────────────────────┬───────┬───────────┐
  │ ID  │   Categoría    │       Problema        │                    Ubicación                     │         Evidencia         │         Impacto          │ Prob. │ Severidad │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ S1  │ Seguridad      │ .env con secretos     │ .env, .gitignore                                 │ passwords en claro; no    │ Fuga de credenciales /   │ Alta  │ Alto      │
  │     │                │ versionado            │                                                  │ ignorado                  │ reuso en prod            │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │     │                │ Bearer token en       │ create_document_service.py:188,                  │ auth_token                │                          │       │           │
  │ S2  │ Seguridad      │ mensajes y Redis      │ redis_outbox_lite.py:96-114,                     │ serializado/persistido    │ Robo/replay de tokens    │ Media │ Alto      │
  │     │                │ (at-rest)             │ base_consumer.py:122-126                         │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ A1  │ Arquitectura   │ BD compartida + FK    │ orm/document.py:14-21                            │ FK a chat.id inexistente  │ Acoplamiento de          │ Alta  │ Alto      │
  │     │                │ cross-service         │                                                  │ aquí                      │ datos/despliegue         │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ D1  │ BD/Perf        │ Faltan índices en     │ orm/document.py, orm/fragment.py                 │ sin index/migraciones     │ Degradación de consultas │ Alta  │ Alto      │
  │     │                │ columnas de filtro    │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ D2  │ BD/Perf        │ Sin índice ANN para   │ orm/fragment.py:32                               │ VECTOR sin HNSW/IVFFlat   │ KNN exacto = no escala   │ Alta  │ Alto      │
  │     │                │ vector                │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ T1  │ Testing        │ Cobertura ~4%         │ test/ (1150 LOC)                                 │ 15 archivos vs 26k LOC    │ Regresiones no           │ Alta  │ Alto      │
  │     │                │                       │                                                  │                           │ detectadas               │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ S3  │ Seguridad      │ /metrics sin auth     │ authentication_middleware.py:14                  │ path excluido             │ Exposición de métricas   │ Media │ Medio     │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ S4  │ Seguridad      │ Rate limit fail-open  │ rate_limiter.py:42-51                            │ retorno sin límite si no  │ Abuso/DoS si Redis cae   │ Media │ Medio     │
  │     │                │                       │                                                  │ hay Redis                 │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ A2  │ Arquitectura   │ Sin migraciones       │ repo                                             │ no Alembic                │ Schema drift             │ Alta  │ Medio     │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ A3  │ Arquitectura   │ Idempotencia no       │ idempotency.py + grep                            │ sin uso en controllers    │ Documentos duplicados    │ Media │ Medio     │
  │     │                │ cableada              │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ O1  │ Observabilidad │ Sin tracing           │ global                                           │ no OTel/propagación       │ Difícil diagnóstico E2E  │ Media │ Medio     │
  │     │                │ distribuido           │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ T2  │ Testing        │ Sin CI/CD             │ repo                                             │ sin pipelines             │ Gates no aplicados       │ Alta  │ Medio     │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ C3  │ Calidad        │ Authz inconsistente   │ document_download_service.py:166                 │ divergencia               │ Confusión/errores        │ Media │ Medio     │
  │     │                │ (header vs fallback)  │                                                  │                           │ futuros                  │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ S5  │ Seguridad      │ CORS * por defecto    │ .env:7, cors_configuration.py                    │ default amplio            │ Riesgo si mal config     │ Baja  │ Bajo      │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ S6  │ Seguridad      │ X-Request-ID sin      │ logging_middleware.py:21                         │ reflejo en header/log     │ Log-bloat                │ Baja  │ Bajo      │
  │     │                │ límite                │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ D3  │ BD             │ index=True redundante │ document.py:12                                   │ duplicado                 │ Cosmético                │ Baja  │ Bajo      │
  │     │                │  en PK                │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ A4  │ Arquitectura   │ startup monolítico    │ dependencies.py:184                              │ ~390 líneas               │ Mantenibilidad/test      │ Media │ Bajo      │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ O2  │ Observabilidad │ Sin métricas de       │ global                                           │ solo HTTP                 │ Visibilidad limitada     │ Media │ Bajo      │
  │     │                │ negocio               │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ C1  │ Calidad        │ Duplicación de        │ 2 providers                                      │ código idéntico           │ DRY                      │ Baja  │ Bajo      │
  │     │                │ helpers bearer        │                                                  │                           │                          │       │           │
  ├─────┼────────────────┼───────────────────────┼──────────────────────────────────────────────────┼───────────────────────────┼──────────────────────────┼───────┼───────────┤
  │ C2  │ Calidad        │ Deps sin pin / sin    │ requirements.txt                                 │ >=                        │ Builds no reproducibles  │ Media │ Bajo      │
  │     │                │ lock                  │                                                  │                           │                          │       │           │
  └─────┴────────────────┴───────────────────────┴──────────────────────────────────────────────────┴───────────────────────────┴──────────────────────────┴───────┴───────────┘

  ---
  FASE 4 — DEUDA TÉCNICA

  - Arquitectónica: BD compartida con FKs entre dominios (A1) y ausencia de migraciones (A2). Causa: arranque rápido sobre una BD común. Consecuencia: despliegues acoplados,
  imposibilidad de evolucionar el esquema de forma independiente. Riesgo futuro: un cambio en el servicio de chat rompe este servicio; migraciones manuales propensas a drift.
  - De código: duplicación de helpers (C1), startup monolítico (A4). Consecuencia: fricción de mantenimiento. Riesgo bajo.
  - Operativa: sin CI/CD (T2), sin tracing (O1), sin lockfile (C2). Consecuencia: despliegues sin red de seguridad automatizada y diagnóstico E2E difícil. Riesgo: defectos llegan a
  prod; incidentes lentos de resolver.
  - De seguridad: secretos en VCS (S1), token de usuario at-rest/en broker (S2), rate-limit fail-open (S3/S4). Riesgo: compromiso de credenciales/tokens, abuso de API.
  - De testing: ~4% de cobertura (T1) concentrada en controllers; el núcleo de negocio (ingesta, embeddings, grafo, outbox) carece de pruebas. Riesgo: regresiones silenciosas en la
  lógica más crítica y compleja.

  ---
  FASE 5 — PLAN DE MEJORA PRIORIZADO

  1) Críticos inmediatos

  1. Sacar .env* del control de versiones (S1): añadir a .gitignore, rotar todas las credenciales comprometidas, mover a gestor de secretos. Beneficio: elimina fuga directa.
  Complejidad: baja. Riesgo de no hacerlo: compromiso de toda la malla de servicios.
  2. Confirmar/crear índices (D1, D2): verificar en la BD real la existencia de índices en document(chat_id, deleted_at, status, created_at), fragment(document_id) y un índice
  HNSW/IVFFlat sobre fragment.vector. Beneficio: rendimiento y escalabilidad del RAG. Complejidad: media.
  3. Reducir exposición del token de usuario (S2): cifrar el auth_token en el outbox o sustituir por un token de servicio de corta vida / patrón de delegación; minimizar TTL.
  Complejidad: media-alta.

  2) Corto plazo

  4. Introducir CI/CD que ejecute ruff+mypy+pytest y escaneo de dependencias (T2, C2 con lockfile/hashes).
  5. Proteger /metrics (red interna o auth) y endurecer rate limiting (fail-closed o degradación controlada; clave basada en identidad autenticada) (S3, S4).
  6. Cablear idempotencia real en POST /document usando la clave + marcador en Redis (A3).

  3) Medio plazo

  7. Adoptar Alembic y versionar el esquema (A2).
  8. Tests del núcleo (servicios de ingesta/grafo, repos, outbox, consumers) hasta un umbral (p. ej. ≥60%) (T1).
  9. Tracing distribuido (OpenTelemetry) propagando contexto por HTTP y mensajes (O1) + métricas de negocio (O2).

  4) Largo plazo

  10. Resolver el acoplamiento de BD (A1): separar el esquema por servicio o sustituir FKs cross-service por referencias lógicas + verificación por API/eventos.
  11. Refactor de dependencies.py en módulos de bootstrap por subsistema (A4) y unificar helpers bearer (C1, C3).

  ---
  FASE 6 — EVALUACIÓN FINAL

  ┌────────────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │   Dimensión    │ Score  │                                                         Justificación basada en evidencia                                                         │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Arquitectura   │ 78/100 │ Hexagonal limpia, interfaces, DI, outbox+reconciliación, circuit breaker. Penaliza BD compartida con FKs cross-service (A1), ausencia de          │
  │                │        │ migraciones (A2) e idempotencia muerta (A3).                                                                                                      │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Seguridad      │ 62/100 │ Bases sólidas (SQL/Cypher parametrizados, validación de upload, authz fail-closed, sin fuga en errores). Penaliza secretos en VCS (S1), token     │
  │                │        │ at-rest/en broker (S2), /metrics abierto (S3) y rate-limit fail-open (S4).                                                                        │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Mantenibilidad │ 72/100 │ Código consistente, tipado, excepciones por módulo, sin artefactos de debug. Penaliza ~4% de tests (T1), duplicación (C1), inconsistencias (C3) y │
  │                │        │  startup monolítico (A4).                                                                                                                         │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Escalabilidad  │ 58/100 │ Async, pooling, prefetch, paginación acotada, outbox. Penaliza fuerte la incertidumbre/ausencia de índices ANN y secundarios (D1, D2) en un       │
  │                │        │ servicio vector-intensivo, y la BD compartida.                                                                                                    │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Observabilidad │ 70/100 │ Logging estructurado con redacción, request_id, readiness con sondas reales, Prometheus. Penaliza falta de tracing (O1) y de métricas de negocio  │
  │                │        │ (O2).                                                                                                                                             │
  ├────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Calidad        │ 72/100 │ Ingeniería de buen nivel y patrones maduros, lastrada por testing insuficiente, gaps operativos (CI/CD, secretos) y dudas de rendimiento en la    │
  │ general        │        │ capa de datos.                                                                                                                                    │
  └────────────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Veredicto para puesta en producción empresarial: el servicio tiene fundamentos de ingeniería de buena calidad, pero no está listo para producción sin antes resolver los críticos:
  secretos fuera de VCS + rotación (S1), confirmación de índices (incl. ANN) (D1/D2), manejo del token de usuario (S2) y un mínimo de CI + pruebas del núcleo (T2/T1).
