  INFORME DE AUDITORÍA — aura-chat-service

  ▎ Modo solo lectura. No se modificó, creó ni eliminó ningún archivo. Todas las conclusiones citan evidencia concreta. Donde no pude verificar algo, lo indico explícitamente.
  
  Nota de alcance: El repositorio contiene 9 apps de tipo artifact casi idénticas en estructura (artifact_report, artifact_checklist, artifact_timeline, artifact_quiz,
  artifact_lessons_learned, artifact_decision_brief, artifact_document_summary, artifact_document_action). Inspeccioné en profundidad artifact_message, chat, membership, assistant,
  artifact y todo core/; de las demás leí estructura, tamaños y un representante (artifact_message/export_service, checklist). Las conclusiones sobre duplicación se basan en esa
  muestra + conteos.

  ---
  FASE 1 — INVENTARIO COMPLETO

  1.1 Estructura del proyecto

  aura_chat_service/        # Proyecto Django
    settings/ base|development|production|test
    asgi.py  urls.py  wsgi.py
  core/                     # Infraestructura transversal (sin lógica de dominio)
    authentication/         # Middleware HTTP + WS, provider con caché Redis de tokens
    authorization/          # AccessControl + catálogo de permisos (string-based)
    clients/                # llm_client, http_client, notification, document_processing, transcription
    exceptions/             # ServiceException jerárquico + handler DRF
    health/  middleware/  models/  openapi/  pagination/  validators/
  apps/
    chat/                   # Chats, share links, consumer WS, presence, locks, rate-limit
    membership/             # Membresías, roles, invitaciones (HTTP + internal)
    artifact/               # Cabecera unificada Artifact + feedback/bookmark/pin/thread
    artifact_message/       # Mensajes (sobre Artifact) + export
    artifact_report|checklist|timeline|quiz|lessons_learned|
    decision_brief|document_summary|document_action/   # 8 tipos de artifact IA
    assistant/              # "Custom GPTs": admins crean, usuarios usan
    message/  checklist/  report/   # ⚠️ APPS LEGADAS: solo quedan __pycache__, sin .py
  test/                     # unit/ + integration/ + test_*.py (parcialmente roto)
  Dockerfile  requirements*.txt  pytest.ini  ruff.toml
  .env  .env.docker         # ⚠️ versionados en git

  Responsabilidad por capa (patrón consistente): views (DRF, validación + OpenAPI) → services (lógica + autorización + transacciones + broadcast WS) → repositories (acceso ORM) →
  models (todos managed=False). El acoplamiento sigue la dirección correcta (vista→servicio→repo); no hay acceso a ORM desde vistas.

  1.2 Arquitectura

  - Estilo: monolito modular Django + DRF con capas tipo layered/service-repository; ASGI (Daphne) con Django Channels para WebSocket; comunicación inter-servicio vía HTTP (httpx)
  con reenvío del JWT del usuario.
  - Patrones presentes: Repository, Service Layer, singletons de módulo (chat_service = ChatService()), Strategy ligero (ChatAIMode, complete_extractor), DTOs (@dataclass en
  llm_client), excepciones de dominio jerárquicas, idempotencia/locks distribuidos en Redis (Lua scripts), reference-counted presence.
  - Cohesión: alta dentro de core y de las apps activas. Flujo de datos: request → AuthenticationMiddleware (valida token contra auth-service, cachea en Redis) → DRF view → service
  → repo → Postgres; eventos en tiempo real vía channel_layer.group_send a chat_{id}.
  - Flujo de dependencias: correcto en general; hay imports diferidos dentro de funciones para romper ciclos (chat_service.delete_chat importa artifact_service localmente;
  chat_repository importa modelos de membership dentro de funciones). Es un code smell que delata dependencia circular latente entre chat ↔ artifact ↔ membership.

  1.3 Dependencias (requirements.txt)

  ┌─────────────────────────────────────┬─────────────────────────────┬────────────────────────┬───────────────────────────────────────────────────────────────────────────────┐
  │               Paquete               │          Propósito          │        Uso real        │                                 Riesgo / Nota                                 │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ Django 6.0.4                        │ Framework                   │ Núcleo                 │ 6.0 es muy reciente; verificar compatibilidad de libs y soporte LTS           │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ djangorestframework 3.16            │ API REST                    │ Intenso                │ OK                                                                            │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ channels[daphne] 4.2 /              │ WebSocket/ASGI              │ Consumer               │ OK                                                                            │
  │ channels-redis 4.2.1                │                             │                        │                                                                               │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ redis >=4.6,<6                      │ Caché, locks, rate-limit,   │ Intenso                │ OK                                                                            │
  │                                     │ presence                    │                        │                                                                               │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ psycopg[binary] 3.2.6               │ Postgres                    │ Núcleo                 │ [binary] no recomendado en prod (usar build)                                  │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ httpx 0.28.1                        │ Clientes inter-servicio     │ Intenso                │ OK                                                                            │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ faster-whisper 1.1.1                │ Transcripción audio         │ apps/artifact/audio.py │ Pesado: modelo embebido en imagen; corre in-process dentro del web server →   │
  │                                     │                             │                        │ riesgo de bloqueo/CPU/memoria                                                 │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ drf-spectacular 0.29                │ OpenAPI                     │ Schema                 │ OK                                                                            │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ django-prometheus 2.3.1             │ Métricas                    │ Middleware + /metrics  │ OK                                                                            │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ python-json-logger 2.0.7            │ Logs JSON                   │ Logging                │ OK                                                                            │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ xhtml2pdf 0.2.16 + python-bidi +    │ Export PDF                  │ export_services        │ xhtml2pdf es lento y CPU-bound; mitigado con timeout + thread                 │
  │ markdown                            │                             │                        │                                                                               │
  ├─────────────────────────────────────┼─────────────────────────────┼────────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ python-decouple 3.8                 │ Config env                  │ settings               │ OK                                                                            │
  └─────────────────────────────────────┴─────────────────────────────┴────────────────────────┴───────────────────────────────────────────────────────────────────────────────┘

  Aparentemente innecesaria / a revisar: faster-whisper acoplado al servicio de chat es discutible arquitectónicamente (debería ser el document-processing o un servicio de
  transcripción dedicado). No detecté dependencias muertas en requirements.txt.

  ---
  FASE 2 — AUDITORÍA TÉCNICA

  2.1 Código

  Código muerto (CRÍTICO en mantenibilidad):
  - apps/message/, apps/checklist/, apps/report/ ya no tienen archivos .py — solo quedan directorios __pycache__/*.pyc (evidencia: find apps/message apps/checklist apps/report
  -name '*.py' → 0 resultados; pero sí existen los .pyc). Son apps eliminadas a medias. No están en INSTALLED_APPS (settings/base.py:25-37), confirmando que están muertas.
  - Los .pyc huérfanos pueden resucitar imports accidentalmente si alguien ejecuta con esos paths en el PYTHONPATH.

  Duplicación (DRY) — ALTA:
  - core/clients/llm_client.py (1142 líneas): ~14 pares de métodos casi idénticos (generate_X / generate_X_stream_events). Cada uno repite el mismo bloque if system_prompt:
  stripped = system_prompt.strip(); if stripped: payload[...] y el mismo logging/post. Es el mayor foco de duplicación del repo.
  - Los services/export_service.py de cada artifact (133–242 líneas cada uno, 8+ copias) repiten CSS, _build_pdf, _safe_link_callback, _render_markdown. Evidencia: mismos
  nombres/estructura en artifact_message/export_service.py y conteos equivalentes en los demás.
  - Los services/*_service.py de cada artifact replican el patrón create/list/get/update/delete + permisos.

  Funciones largas / responsabilidad excesiva:
  - MessageService._iter_ai_stream_group_payloads (message_service.py:412-547): ~135 líneas, múltiples responsabilidades (parseo SSE, acumulación, persistencia, fallback, manejo de
  errores). Difícil de testear unitariamente.
  - ChatConsumer._handle_chat_message (chat_consumer.py:233-376): valida, rate-limita, cancela tareas previas, adquiere lock, persiste, lanza tarea de fondo — demasiadas
  responsabilidades en un método.

  Comentarios/limpieza: No se hallaron TODO/FIXME/print()/pdb en apps ni core (grep limpio). Buena señal. Imports sin uso: ruff.toml mantiene el set por defecto (pyflakes), pero no
  hay gate de CI que lo ejecute (ver 2.7).

  KISS/YAGNI: El catálogo de permisos (core/authorization/permissions.py, 171 líneas, ~150 constantes) está sobre-dimensionado respecto a lo que los servicios consumen; muchos
  MANAGE_*/EXPORT_* no aparecen referenciados en services (posible YAGNI / permisos definidos pero no aplicados — requiere verificación de uso por permiso).

  2.2 Arquitectura

  - Dependencias circulares latentes: resueltas con imports locales dentro de funciones (chat_service.py:171,286; chat_repository.py:24,38,55). Funciona pero es deuda; señala
  límites de módulo mal trazados entre chat, artifact y membership.
  - Fuga de abstracción: roles comparados como strings mágicos (role == "reader", "owner", "active") en consumer y services (chat_consumer.py:263, message_service.py:624) en lugar
  de usar siempre ChatMembership.Role/Status (que sí existen y se usan en otros sitios — inconsistencia).
  - Lógica de broadcast WS duplicada en cada service (_broadcast_* repetidos en chat_service, membership_service, message_service) en vez de un helper común.

  2.3 Base de datos

  - managed = False en los 25 modelos (grep "managed = False" → 25). El esquema no vive en este repo: no hay migraciones (find ... migrations → vacío, no existen directorios
  migrations/). Implicaciones:
    - No hay esquema-como-código aquí → riesgo alto de drift entre modelos Python y tablas reales.
    - Los tests no pueden crear el schema automáticamente (managed=False ⇒ Django no crea tablas en la BD de test) — agrava el estado roto de los tests de integración.
    - No verificable desde este repo: índices, constraints, FKs reales en Postgres. Los modelos declaran db_index=True (p.ej. soft_delete.deleted_at) y FKs, pero al ser no
  gestionados, no garantizan que existan en la BD.
  - Consultas: generalmente buenas. chat_repository.get_chats_for_member usa subqueries anotadas para member_count, unread_count, pinned_at evitando N+1;
  message_repository.get_messages_by_chat usa select_related("artifact") + Exists/FilteredRelation. Riesgo: unread_count usa subquery anidada (OuterRef(OuterRef)) y se ejecuta por
  cada fila de la página — costo aceptable con paginación, pero caro si crece el page_size; conviene índice compuesto (artifact.source_chat_id, type, created_at) en BD (no
  verificable aquí).
  - Concurrencia: uso correcto de select_for_update() (get_by_id_for_update, update_role) y locks Redis para la respuesta IA. Bien.

  2.4 API

  - Contratos REST consistentes (/api/v1/...), versionado por path. Errores normalizados por custom_exception_handler con error, detail, status_code, correlation_id.
  - Validación: vía serializers DRF (is_valid(raise_exception=True)). En transcribe_view la validación de tipo/size es manual pero correcta.
  - Inconsistencia de versionado: todo es /api/v1/ sin estrategia documentada de evolución; los DTOs de respuesta de cada artifact son ad-hoc.
  - Doc/idioma mixto: descripciones OpenAPI mezclan español e inglés (settings/base.py TAGS), y mensajes de error en inglés vs choices en español (Artifact.Mode "Directo").
  Inconsistencia de localización.

  2.5 Seguridad

  ┌────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────┬────────────────────────────────────────┐
  │      Hallazgo      │                                                  Evidencia                                                   │               Severidad                │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Secretos           │ git ls-files → .env, .env.docker rastreados; SECRET_KEY=django-insecure-..., DB_PASSWORD=aura_password,      │ Crítico                                │
  │ versionados en git │ NOTIFICATION_INTERNAL_API_TOKEN=dev-notification-internal-token                                              │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ .gitignore no      │ .gitignore no lista .env* (solo .dockerignore lo hace) → futuros secretos se commitearán                     │ Alto                                   │
  │ excluye .env       │                                                                                                              │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Docker corre en    │ .env.docker:1 DJANGO_SETTINGS_MODULE=...development + DEBUG=True; development.py activa                      │ Crítico (si ese env llega a prod)      │
  │ modo desarrollo    │ CORS_ALLOW_ALL_ORIGINS=True y throttling 600/1200. La imagen se despliega con DEBUG y CORS abierto           │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ JWT en query       │                                                                                                              │ Medio (limitación del protocolo, pero  │
  │ string de          │ websocket_auth_middleware.py:37-46 lee ?token=. Los tokens quedan en logs de proxy, access logs, historial   │ mitigable con subprotocol/cookie)      │
  │ WebSocket          │                                                                                                              │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ SECRET_KEY sin     │ base.py:9 config("SECRET_KEY") — bien que sea obligatorio, pero el valor provisto es inseguro                │ Alto                                   │
  │ default seguro     │                                                                                                              │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Rate-limit falla   │ ws_rate_limit.py y locks: ante RedisError retornan True/permiten. Decisión de disponibilidad sobre seguridad │ Medio                                  │
  │ abierto            │  — discutible para abuso                                                                                     │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Permisos correctos │ AccessControl.require_permissions + checks de membresía/rol en cada service. WS valida membresía antes de    │ OK                                     │
  │                    │ aceptar (chat_consumer.py:67-72)                                                                             │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Sin inyección SQL  │ Solo ORM parametrizado; Lua usa KEYS/ARGV; sin .raw()/.extra()/cursor peligrosos (grep limpio)               │ OK                                     │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Export PDF sin     │ _safe_link_callback retorna "" (bloquea fetch remoto) + strip de tags peligrosos + timeout                   │ OK (defensa razonable)                 │
  │ SSRF               │ (export_service.py:107,128)                                                                                  │                                        │
  ├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────┤
  │ Carga de audio     │ transcribe_view.py:57-66 valida content-type y tamaño (25MB)                                                 │ OK                                     │
  │ limitada           │                                                                                                              │                                        │
  └────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────┴────────────────────────────────────────┘

  2.6 Performance / Escalabilidad

  - Whisper in-process (WHISPER_PRELOAD=True en .env.docker, WHISPER_MAX_CONCURRENCY=2): la transcripción CPU-bound corre dentro del proceso ASGI; bajo carga bloquea el event loop
  / consume CPU del web server. Cuello de botella de escalabilidad y de aislamiento de fallos. Alto.
  - PDF (xhtml2pdf) también CPU-bound; mitigado con ThreadPoolExecutor(max_workers=1) + timeout 30s, pero compite por CPU del proceso.
  - Clientes HTTP: pooling correcto (httpx.Limits, keep-alive), timeouts configurables, reintentos con backoff+jitter. Bien.
  - Tareas IA de fondo retenidas en _BACKGROUND_AI_TASKS (set a nivel de proceso): no sobreviven a reinicios y no se reparten entre réplicas — en multi-instancia el stream solo
  llega a los miembros conectados a la misma instancia salvo que channels-redis lo distribuya (sí lo hace para group_send, pero la tarea corre en una sola instancia). Aceptable,
  pero a documentar.
  - CONN_MAX_AGE=60 y connect_timeout=5: razonable. Sin select_related en algunos serializers de respuesta (no verificado exhaustivamente por artifact).

  2.7 Observabilidad

  - Fuerte: logging JSON estructurado con correlation_id (base.py:371-422), RequestLoggingMiddleware (método, path, status, duración, user_id, IP), Prometheus middleware +
  /metrics, health probes K8s-style (liveness/readiness/startup).
  - Carencias: no hay tracing distribuido (OpenTelemetry) pese a ser arquitectura multi-servicio con reenvío de JWT; no hay métricas de negocio/custom (solo las HTTP por defecto de
  django-prometheus); el correlation_id no se propaga explícitamente a los servicios downstream en build_service_user_headers (solo reenvía el token, no el correlation-id) — rompe
  la traza entre servicios. Medio.
  - Logs sensibles: no se loguea el body ni el token; user_id/IP sí (esperable). Aceptable.

  2.8 Testing

  - Suite parcialmente rota (ALTO): numerosos archivos importan módulos eliminados (apps.message, apps.checklist, apps.report):
    - test/integration/conftest.py, test_chat_integration.py, test_features_integration.py, test_message_integration.py, test_report_integration.py, test_checklist_integration.py.
    - test/test_bookmarks.py, test_exports.py, test_feedback.py, test_feedback_analytics.py, test_messages.py, test_pins.py, test_threads.py.
    - test/unit/{message,checklist,report,artifact}/...
    - Estos fallan en colección (ImportError). La nota de memoria del proyecto confirma: "ignore pre-existing collection errors/failures".
  - pytest.ini lista python_files que incluye carpetas cuyos tests están rotos → ruido permanente en CI.
  - Tests de integración con managed=False: sin migraciones, la BD de test no tendrá tablas → no pueden correr salvo contra una BD real preparada. Esto convierte gran parte de
  "integration" en no ejecutable en CI estándar.
  - Cobertura real efectiva: los unit tests que sí cargan (chat, membership, assistant, shared_link, core/test_llm_client con solo 2 tests para 1142 líneas) están desbalanceados.
  llm_client (el archivo más grande y crítico) tiene cobertura mínima.

  ---
  FASE 3 — MATRIZ DE HALLAZGOS

  ┌─────┬──────────────────┬────────────────────────────┬──────────────────────────────────────────────┬─────────────────────────────┬──────────────────────┬──────┬──────────┐
  │ ID  │    Categoría     │          Problema          │                  Ubicación                   │          Evidencia          │       Impacto        │ Prob │ Severida │
  │     │                  │                            │                                              │                             │                      │  .   │    d     │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │     │                  │ Secretos versionados en    │                                              │ git ls-files los lista; SEC │ Exposición de        │      │          │
  │ F01 │ Seguridad        │ git                        │ .env, .env.docker                            │ RET_KEY/DB_PASSWORD/token   │ credenciales         │ Alta │ Crítico  │
  │     │                  │                            │                                              │ visibles                    │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F02 │ Config/Seguridad │ Imagen Docker en developme │ .env.docker:1-4, development.py:3-5          │ settings dev con            │ Fuga de stacktraces, │ Alta │ Crítico  │
  │     │                  │ nt+DEBUG=True+CORS abierto │                                              │ CORS_ALLOW_ALL_ORIGINS=True │  CSRF/CORS           │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │     │                  │ Suite importa apps         │ test/integration/*, test/test_*, test/unit/{ │ imports apps.message/.check │ CI inservible /      │      │          │
  │ F03 │ Testing          │ eliminadas → collection    │ message,report,checklist,artifact}           │ list/.report sin .py        │ regresiones no       │ Alta │ Alto     │
  │     │                  │ errors                     │                                              │                             │ detectadas           │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │     │                  │ Dirs apps/message|checklis │                                              │ find -name '*.py'→0, .pyc   │ Confusión,           │      │          │
  │ F04 │ Código muerto    │ t|report solo con .pyc     │ esas carpetas                                │ presentes                   │ resurrección de      │ Alta │ Alto     │
  │     │                  │                            │                                              │                             │ imports              │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │     │                  │ Sin migraciones; 25        │                                              │                             │                      │      │          │
  │ F05 │ BD               │ modelos managed=False y    │ todos los models.py                          │ grep managed=False→25; sin  │ Drift de esquema,    │ Medi │ Alto     │
  │     │                  │ schema externo no          │                                              │ migrations/                 │ tests no ejecutables │ a    │          │
  │     │                  │ versionado                 │                                              │                             │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F06 │ Seguridad        │ .gitignore no ignora .env* │ .gitignore                                   │ ausencia de .env            │ Re-exposición futura │ Alta │ Alto     │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F07 │ Mantenibilidad/D │ 14 pares de métodos        │ core/clients/llm_client.py                   │ métodos                     │ Costo de cambio,     │ Alta │ Medio    │
  │     │ RY               │ duplicados                 │                                              │ generate_*/*_stream_events  │ bugs                 │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F08 │ DRY              │ export_service.py          │ apps/artifact_*/services/export_service.py   │ CSS/_build_pdf repetidos    │ Mantenimiento        │ Alta │ Medio    │
  │     │                  │ duplicado x8 artifacts     │                                              │                             │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F09 │ Escalabilidad    │ Whisper CPU-bound          │ apps/artifact/audio.py, .env.docker          │ preload + concurrency 2     │ Bloqueo del web      │ Medi │ Alto     │
  │     │                  │ in-process                 │ WHISPER_*                                    │                             │ server               │ a    │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F10 │ Seguridad        │ JWT en query string WS     │ websocket_auth_middleware.py:37              │ params.get("token")         │ Token en logs        │ Medi │ Medio    │
  │     │                  │                            │                                              │                             │                      │ a    │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F11 │ Observabilidad   │ correlation_id no se       │ authentication_provider.build_service_user_h │ solo reenvía Authorization  │ Traza rota entre     │ Alta │ Medio    │
  │     │                  │ propaga a downstream       │ eaders                                       │                             │ servicios            │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F12 │ Arquitectura     │ Dependencias circulares    │ chat_service.py:171,286,                     │ imports dentro de funciones │ Fragilidad           │ Medi │ Medio    │
  │     │                  │ vía imports locales        │ chat_repository.py:24                        │                             │                      │ a    │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F13 │ Calidad          │ Roles/estados como strings │ chat_consumer.py:263, message_service.py:624 │ == "reader", "owner"        │ Errores silenciosos  │ Medi │ Medio    │
  │     │                  │  mágicos                   │                                              │                             │                      │ a    │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │     │                  │ Rate-limit/lock            │                                              │                             │                      │      │          │
  │ F14 │ Resiliencia      │ "fail-open" ante           │ ws_rate_limit.py:52,68,96                    │ return True en except       │ Abuso si Redis cae   │ Baja │ Medio    │
  │     │                  │ RedisError                 │                                              │                             │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F15 │ CI/CD            │ No existe pipeline         │ sin .github/, sin docker-compose             │ ls raíz                     │ Sin gates de         │ Alta │ Alto     │
  │     │                  │                            │                                              │                             │ calidad/seguridad    │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F16 │ Testing          │ llm_client (1142 líneas)   │ test/unit/core/test_llm_client.py            │ grep def test_→2            │ Riesgo en componente │ Alta │ Medio    │
  │     │                  │ con ~2 tests               │                                              │                             │  crítico             │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F17 │ Calidad          │ Funciones largas/multi-res │ message_service.py:412, chat_consumer.py:233 │ ~135/~143 líneas            │ Testabilidad         │ Medi │ Bajo     │
  │     │                  │ ponsabilidad               │                                              │                             │                      │ a    │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F18 │ Dependencias     │ psycopg[binary] en prod    │ requirements.txt:10                          │ [binary]                    │ Rendimiento/estabili │ Baja │ Bajo     │
  │     │                  │                            │                                              │                             │ dad                  │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F19 │ API              │ Idioma mixto ES/EN en      │ settings/base.py TAGS, artifact.py:20        │ textos mezclados            │ UX/consistencia      │ Alta │ Bajo     │
  │     │                  │ contratos/choices          │                                              │                             │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F20 │ Seguridad        │ ALLOWED_HOSTS=["*"] y CORS │ settings/test.py:4-5                         │ wildcard                    │ Solo afecta tests    │ Baja │ Bajo     │
  │     │                  │  abierto en test           │                                              │                             │                      │      │          │
  ├─────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────┼──────────────────────┼──────┼──────────┤
  │ F21 │ Dependencias     │ Django 6.0 muy reciente    │ requirements.txt:1                           │ pin 6.0.4                   │ Riesgo de soporte de │ Medi │ Bajo     │
  │     │                  │ (compatibilidad)           │                                              │                             │  libs                │ a    │          │
  └─────┴──────────────────┴────────────────────────────┴──────────────────────────────────────────────┴─────────────────────────────┴──────────────────────┴──────┴──────────┘

  ---
  FASE 4 — DEUDA TÉCNICA

  Deuda arquitectónica
  - Causa: migración incompleta del modelo "message/checklist/report" al modelo unificado "artifact" (apps viejas borradas a medias; ciclos resueltos con imports locales).
  Consecuencia: límites de módulo difusos, .pyc huérfanos, riesgo de resurrección. Riesgo futuro: refactors arriesgados, onboarding lento.
  - Causa: transcripción/PDF CPU-bound dentro del proceso ASGI. Consecuencia: el web server hace trabajo pesado. Riesgo futuro: degradación bajo carga, difícil de escalar
  independientemente.

  Deuda de código
  - Causa: generación de código por copia para cada tipo de artifact y cada endpoint LLM. Consecuencia: llm_client y los 8 export_service divergen con el tiempo. Riesgo futuro:
  bugs inconsistentes, alto costo de cambio.
  - Causa: strings mágicos para roles/estados pese a existir enums. Riesgo: errores que el type-checker no detecta.

  Deuda operativa
  - Causa: el esquema vive fuera del repo y no hay migraciones ni docker-compose ni CI. Consecuencia: despliegue/arranque no reproducibles desde el repo; sin compose para levantar
  BD/Redis/servicios. Riesgo futuro: drift de esquema en producción, "funciona en mi máquina".
  - Causa: DJANGO_SETTINGS_MODULE=development en .env.docker. Consecuencia: contenedor inseguro por defecto. Riesgo: despliegue accidental con DEBUG.

  Deuda de seguridad
  - Causa: .env versionado + .gitignore incompleto. Consecuencia: secretos en el historial git (no se eliminan rotando el archivo). Riesgo futuro: compromiso si el repo se filtra;
  requiere rotar credenciales y purgar historial.

  Deuda de testing
  - Causa: renombrado de apps sin actualizar tests + managed=False sin estrategia de BD de test. Consecuencia: gran parte de la suite no colecciona/ejecuta; CI no protege. Riesgo
  futuro: regresiones silenciosas; falsa sensación de cobertura.

  ---
  FASE 5 — PLAN DE MEJORA (roadmap priorizado)

  1) Crítico / inmediato

  1. Rotar todos los secretos (SECRET_KEY, DB_PASSWORD, NOTIFICATION_INTERNAL_API_TOKEN) y purgar .env/.env.docker del historial git (BFG/git filter-repo). Añadir .env* a
  .gitignore y mover a gestor de secretos. Justificación: F01/F06. Riesgo de no hacerlo: compromiso total. Complejidad: Media.
  2. Separar settings de despliegue de desarrollo: el contenedor debe usar settings.production (DEBUG=False, CORS restringido) por defecto. Justificación: F02. Complejidad: Baja.
  3. Reparar o cuarentenar la suite de tests: actualizar imports a apps.artifact_*/apps.chat, o excluir explícitamente lo roto en pytest.ini, hasta migrar. Justificación: F03.
  Complejidad: Media.

  2) Corto plazo

  4. Eliminar dirs muertos apps/message|checklist|report (incluidos .pyc) y limpiar referencias. Beneficio: claridad, evita resurrección. Complejidad: Baja. (F04)
  5. Introducir CI (lint ruff + pytest + chequeo de secretos como gitleaks). Beneficio: gates de calidad/seguridad. Complejidad: Media. (F15)
  6. Documentar y versionar el esquema: dado managed=False, mantener un repositorio/migraciones SQL fuente de verdad y un check de drift; o gestionar las tablas de este servicio
  con Django. Beneficio: reproducibilidad, tests ejecutables. Complejidad: Alta. (F05)

  3) Mediano plazo

  7. Refactor llm_client: un único método parametrizado por endpoint/result_builder, eliminando los 14 pares. Beneficio: −60% líneas, menos bugs. Complejidad: Media. (F07)
  8. Extraer un BaseExportService/módulo común para PDF/Markdown de los artifacts. Complejidad: Media. (F08)
  9. Mover Whisper a un servicio/worker dedicado (o cola) fuera del proceso ASGI. Beneficio: escalabilidad e aislamiento. Complejidad: Alta. (F09)
  10. Propagar correlation_id a downstream en build_service_user_headers. Complejidad: Baja. (F11)

  4) Largo plazo

  11. OpenTelemetry tracing end-to-end + métricas de negocio. (F11)
  12. Eliminar ciclos reorganizando módulos (extraer interfaces compartidas) para quitar imports locales. (F12)
  13. Sustituir strings mágicos por enums en todo el código. (F13)
  14. Política de versionado de API y unificación de idioma en contratos. (F19)

  ---
  FASE 6 — EVALUACIÓN FINAL

  ▎ El código activo es de calidad notablemente alta (transacciones correctas, locks distribuidos bien implementados, manejo de errores y reintentos cuidadoso, autorización
  ▎ consistente, defensa anti-SSRF en PDF, health probes correctas). Las puntuaciones bajan por deuda operativa y de seguridad de configuración, código/tests muertos y duplicación,
  ▎ no por la lógica de dominio.

  Arquitectura — 76/100

  Capas limpias y patrones consistentes (service/repository), buen uso de Channels/Redis. Penaliza: ciclos resueltos con imports locales (F12), Whisper in-process (F09), migración
  a "artifact" incompleta (F04), límites de módulo difusos.

  Seguridad — 52/100

  Buen modelo de autz/autn, sin inyección, PDF sin SSRF, rate-limiting. Penaliza fuerte: secretos en git (F01), Docker en DEBUG/CORS abierto (F02), .gitignore incompleto (F06), JWT
  en query WS (F10), fail-open (F14). Son problemas de configuración/operación, corregibles rápido pero hoy bloqueantes para producción empresarial.

  Mantenibilidad — 60/100

  Código activo legible y bien comentado, ruff configurado. Penaliza: dirs muertos con .pyc (F04), duplicación masiva en llm_client y export (F07/F08), strings mágicos (F13),
  funciones largas (F17).

  Escalabilidad — 70/100

  Async + Redis + Channels + pooling + backoff + rate-limit por usuario. Penaliza: transcripción/PDF CPU-bound en el proceso web (F09), tareas IA atadas a instancia, una sola BD.

  Observabilidad — 72/100

  Logging JSON con correlation_id, Prometheus, probes K8s, request logging. Penaliza: sin tracing distribuido, correlation_id no propagado entre servicios (F11), sin métricas de
  negocio.

  Calidad General — 63/100

  Escalabilidad — 70/100

  Async + Redis + Channels + pooling + backoff + rate-limit por usuario. Penaliza: transcripción/PDF CPU-bound en el proceso web (F09), tareas IA atadas a instancia, una sola BD.

  Observabilidad — 72/100

  Logging JSON con correlation_id, Prometheus, probes K8s, request logging. Penaliza: sin tracing distribuido, correlation_id no propagado entre servicios (F11), sin métricas de
  negocio.

  Calidad General — 63/100

  Promedio ponderado. La ingeniería del happy path es sólida; lo que arrastra la nota es el estado del repositorio como artefacto desplegable: tests rotos (F03/F16), código muerto
  (F04), secretos (F01), sin CI (F15), sin migraciones (F05).

  ---
  Conclusión ejecutiva

  aura-chat-service tiene un núcleo de ingeniería competente pero no está listo para un despliegue empresarial en su estado actual. Los tres bloqueantes son: (1) secretos
  versionados + Docker en modo desarrollo, (2) ausencia de fuente-de-verdad del esquema/migraciones con CI, y (3) una suite de tests rota que no protege contra regresiones.
  Resueltos esos tres y la duplicación de llm_client/exports, el servicio pasaría de "prototipo avanzado" a "candidato a producción".

  ¿Quieres que profundice en algún área concreta (p. ej., revisar los 8 export_service uno a uno, o auditar cada permiso de permissions.py contra su uso real en los services)?
