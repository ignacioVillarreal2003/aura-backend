INFORME DE AUDITORÍA — CAPA DE ORQUESTACIÓN DE LLMs (aura-llm-service)

Modo: solo lectura · Alcance: orquestación, RAG, prompts, streaming, conversación,
inferencia, seguridad, observabilidad.
Stack confirmado: FastAPI ≥0.121, LangGraph ≥0.2, langchain-ollama (ChatOllama),
Ollama (LLM local), Redis (auth-cache + rate-limit), NeMo Guardrails (opcional),
Prometheus, OpenInference/Phoenix (opcional). Recuperación y grafo de conocimiento
delegados por HTTP a servicios externos.

---
FASE 1 — MAPEO DEL SISTEMA

1.1 Arquitectura de orquestación

El servicio expone una capa limpia en cuatro anillos (api → application →
infrastructure → domain). Hay tres motores de orquestación distintos, no uno solo:

Motor: Agente RAG
Archivo: rag_agent_service.py + rag_agent_workflow.py
Patrón: Grafo LangGraph (7 nodos)
Streaming de tokens: ❌  (solo progreso por nodo)
────────────────────────────────────────
Motor: Chat general / RAG conversacional
Archivo: general_chat_service.py
Patrón: Pipeline de procesadores
Streaming de tokens: ✅  (token a token)
────────────────────────────────────────
Motor: Generación estructurada (report, checklist, quiz, timeline, lessons,
decision-brief, y los de processing/)
Archivo: structured_generation_service.py
Patrón: Template Method + procesadores
Streaming de tokens: ❌  (espera respuesta completa, JSON mode)

1.2 Flujo completo de una consulta (agente RAG, POST /api/v1/.../stream)

Cliente
│  (Bearer JWT, body JSON)
▼
Middleware logging  (request_id / X-Request-ID)        logging_middleware.py
▼
Middleware auth     (valida token vs auth-service, cachea en Redis,
               fija contextvar request_token)
authentication_provider_middleware.py
▼
Middleware body-size limit                              body_size_limit_middleware.py
▼
Middleware Guardrails (NeMo self_check_input sobre
                 el último mensaje human)         guardrails_middleware.py
▼
Controller  (Authorizer.require_permissions LLM_AGENT,
       strict_rate_limit)                         rag_agent_controller.py
▼
RagAgentService.execute_stream → RagAgentStateBuilder.build
▼
RagAgentWorkflow.stream  (astream stream_mode=["updates","values"])
▼
┌─ query_analyzer        (LLM #1: reformula + keywords + intent JSON)
├─ graph_context_retriever (HTTP → graph service)
├─ (cond) document_fetcher | context_retriever  (HTTP → document-processing)
├─ answer_synthesizer    (LLM #2: ainvoke, NO stream)
├─ (cond) guardrails      (LLM #3 regla+grounding, opcional LLM #4 redacción)
└─ fallback
▼
sse_response  (heartbeat 15s, cancela tarea pendiente en finally)   sse.py
▼
Cliente (eventos progress… complete)

1.3 Puntos de entrada / salida / dependencias críticas

- Entrada: controllers en app/api/controllers/** (14 dominios). Todo bajo /api/v1,
auth obligatoria salvo health/docs/metrics.
- Salida: OllamaLLMFacade → ChatOllama → Ollama; HttpClient (circuit breaker + retry)
→ document-processing-service, graph-service, auth-service.
- Dependencias críticas (singletons en app.state, construidos en dependencies.py:79):
OllamaLLMFacade (se inicializa en arranque con probe de conectividad), HttpClient,
RedisClient, providers HTTP. Acoplamiento fuerte: todos los servicios reciben el mismo
ollama_facade y http_client por inyección manual en startup_dependencies.
- Acoplamiento notable: la recuperación NO ocurre en este servicio; se delega vía
DocumentContextProvider/GraphContextProvider. El aislamiento multi-tenant depende del
reenvío del JWT (get_request_token() contextvar) al servicio downstream.

---
FASE 2 — AUDITORÍA DE PROMPTS

2.1 Gestión de prompts

- Dónde viven: dispersos en (a) propiedades system_prompt dentro de clases *Settings
(p. ej. rag_agent_settings.py:38-56,72-82,106-120,126-137), y (b) módulos *_prompt.py
por servicio (general_chat_prompt.py, query_reformulation_prompts.py, etc.). Total:
~20+ prompts.
- Versionado: ❌  inexistente. No hay IDs de versión, changelog, ni registro central.
Los prompts son literales en código.
- Reutilización: parcial. augment_system_prompt() (prompt_augmentation.py) y
build_generation_messages() se reutilizan bien; pero cada servicio redefine su propio
system prompt.
- Duplicación: las cláusulas de seguridad anti-inyección están repetidas casi
textualmente en general_chat_prompt.py:21-23, rag_agent_settings.py:114-115 y
prompts.yml. Cambiar la política exige editar múltiples archivos.
- Hardcoding: alto. Prompts, idioma (es-AR), ejemplos few-shot y mensajes de fallback
están incrustados en código.

2.2 Calidad

- Claridad: alta. Los prompts son explícitos, con instrucciones numeradas y formato de
salida definido.
- Modularidad: media. custom_system_prompt permite override por settings, pero no hay
composición de bloques (seguridad / formato / dominio) reutilizables.
- Mantenibilidad: media-baja por duplicación y ausencia de versionado.

2.3 Riesgos

- Prompt injection (operador): AgentRequest.system_prompt y response_style (hasta
10.000 chars) se concatenan al system prompt con una nota textual de precedencia
(_OPERATOR_PRECEDENCE_NOTE, prompt_augmentation.py:1-5). La defensa es solo
lingüística, no estructural — un operador puede intentar sobrescribir reglas. (Riesgo
medio; el operador es un rol autenticado.)
- Context poisoning: el contenido recuperado de documentos se inserta como texto en el
prompt (answer_synthesizer_node, build_context_block). Instrucciones embebidas en
documentos podrían manipular al sintetizador. Mitigación: el prompt de general_chat
trata el contexto como "DATOS" (general_chat_prompt.py:22), y el nodo guardrails
revisa manipulación (rag_agent_settings.py:114-115) — pero el guardrails falla-abierto
(ver Fase 4/7).
- Prompt leakage: el system prompt es estático; el guardrail de entrada bloquea
"mostrame tu system prompt" (prompts.yml:22). Defensa razonable pero dependiente del
LLM clasificador.
- Jailbreak: la única barrera dura es NeMo self_check_input (LLM-judge con few-shots).
Es bypasseable con prompts adversariales no cubiertos por los ejemplos.

---
FASE 3 — AUDITORÍA DE RAG

3.1 Retrieval

- Estrategia: híbrida delegada. ContextRetrieverNode._retrieve
(context_retriever_node.py:56) y ContextRetrievalProcessor._build_request construyen
consultas semánticas + BM25 + rerank + adjacent_chunks y las envían al
document-processing-service. El ranking/re-ranking real ocurre fuera de este servicio.
- Filtros: ninguno explícito aquí (categoría, fecha, tipo). El scoping por
tenant/documento es responsabilidad del downstream vía JWT.
- Intent routing: query_analyzer clasifica question vs document_lookup;
document_lookup activa DocumentFetcherNode que recupera documentos completos
(descubrimiento + fetch por document_id).

3.2 Construcción de contexto

- Selección/ensamblado: build_document_context (context_formatting.py) agrupa
fragmentos por documento, ordena por fragment_index, y recorta a max_context_chars
(10.000). En generation_messages.build_context_block se priorizan adjuntos vs RAG con
attached_reserve_ratio.
- Deduplicación: solo por id (generation_state.py:52-54). No hay deduplicación de
fragmentos solapados/near-duplicate ni de oraciones repetidas → ruido posible.
- Compresión: ContextReductionProcessor implementa un map-reduce multi-pasada
(context_reduction_processor.py) con extracción por lotes. Bien diseñado, pero solo se
activa cuando total > max_context_chars.

3.3 Calidad del contexto — riesgos

- Truncado destructivo (HALLAZGO): content = fragment.content[:remaining]
(context_formatting.py:36) y el corte por presupuesto en _render_fragments cortan a
mitad de palabra/oración, sin marcador de truncado. Riesgo de pérdida de información y
de citas incompletas.
- Pérdida silenciosa por ventana de contexto del modelo (ver Fase 6).
- Ruido: sin dedup semántica, fragmentos redundantes consumen presupuesto.
- Alucinaciones inducidas: el prompt fuerza "EXCLUSIVAMENTE en el contexto" y citas
[Documento #ID], lo que mitiga; pero no hay verificación de que las citas existan
realmente.

3.4 Performance

- Consultas redundantes: en general_chat modo RAG la cadena es: adjuntos →
reformulación base (LLM) → reformulación keywords (LLM) → retrieval → reducción
(N×LLM) → generación. Múltiples llamadas secuenciales (ver Fase 6, latencia).
- Cuello de botella: todo el pipeline RAG-agente es secuencial;
graph_context_retriever y context_retriever podrían paralelizarse pero se ejecutan en
serie por el diseño del grafo.

---
FASE 4 — AUDITORÍA DE STREAMING

4.1 Flujo

- SSE centralizado en sse.py. format_sse_event serializa Pydantic a data: {...}\n\n.
Headers correctos (no-cache, X-Accel-Buffering: no).
- Inicio/fin: el generador del servicio produce eventos tipados
(progress/delta/complete/error).

4.2 Robustez — bien resuelto

- Heartbeat: ping cada 15s vía asyncio.wait(timeout=...) evita timeouts de proxies
(sse.py:29-33).
- Cancelación / desconexión: el finally cancela la tarea pending y suprime
CancelledError (sse.py:41-45) → no deja la coroutine huérfana.
- Backpressure runaway: OllamaLLMStreamingInvoker corta si supera
max_stream_response_chars (100k) (ollama_llm_streaming_invoker.py:103,114).
- Reintentos de stream: solo en el establecimiento del stream (primer chunk); una
interrupción a mitad no se reintenta (correcto, evita duplicar tokens) y se reporta
como error (:121-128).

4.3 Riesgos / hallazgos

- HALLAZGO (UX/latencia): el agente RAG NO hace streaming de tokens.
answer_synthesizer_node usa llm.ainvoke (answer_synthesizer_node.py:93), no astream;
el workflow solo emite progreso por nodo y entrega la respuesta completa en el evento
complete (rag_agent_workflow.py:101-120). El usuario espera toda la generación sin ver
tokens. El general_chat sí hace token-streaming real.
- Streams huérfanos: no se observan; la gestión del finally es correcta.
- Condiciones de carrera: los nodos hacen lazy-init del LLM con asyncio.Lock
(doble-check). Correcto. El grafo se compila una sola vez con lock
(rag_agent_service.py:177-184).

---
FASE 5 — AUDITORÍA DE CONVERSACIONES

5.1 Memoria

- Persistencia: ❌  El servicio es stateless respecto a la conversación. No hay
almacenamiento de historial. Redis se usa solo para cache de tokens de auth y
rate-limiting (redis_client). El historial lo envía el cliente en cada request
(AgentRequest.messages, máx. 50).
- Recuperación/expiración: no aplica (no persiste). El chat_id se reenvía al servicio
de retrieval pero aquí no se valida pertenencia.

5.2 Historial / tokens

- Truncado: por número de mensajes, no por tokens: _MAX_HISTORY_MESSAGES=6 en query
analyzer (query_analyzer_node.py:18,116-119), history_messages_window=4 en generación
(generation_settings.py:14). El formateo de historial en
query_analyzer._format_history no recorta el contenido de cada mensaje → posible
bloat.
- Crecimiento de tokens: controlado por chars, nunca por tokens reales (ver Fase 6).

5.3 Escalabilidad / consistencia

- Concurrencia: servicios singleton compartidos; el grafo LangGraph compilado es
reutilizable entre invocaciones (estado por-invocación). Sin estado mutable compartido
entre requests → seguro para concurrencia.
- HALLAZGO (integridad de conversación): los mensajes assistant del historial
provienen del cliente y se confían como AIMessage (rag_agent_state_builder.py:51). Un
cliente malicioso puede fabricar turnos del asistente para inducir comportamiento
(forma de context/history poisoning).

---
FASE 6 — AUDITORÍA DE INFERENCIA

6.1 Llamadas al modelo

- Retries: OllamaLLMInvoker y el streaming usan tenacity con backoff exponencial (3
intentos, _RETRYABLE_EXCEPTIONS solo errores de red/timeout) — correcto, no reintenta
errores de validación.
- Timeouts: request_timeout=600s por defecto (ollama_llm_facade_settings.py:30). Muy
alto para un endpoint interactivo.
- Circuit breaker: existe a dos niveles: (a) en el arranque del facade
(OllamaLLMFacade, threshold=1, cooldown 30s — ollama_llm_facade.py:24-25); (b) en
HttpClient (aiobreaker) para llamadas HTTP downstream. No hay circuit breaker en las
llamadas runtime al LLM (solo retries). Una saturación de Ollama no abre circuito
durante la operación.
- Rate limits: strict_rate_limit por usuario/ruta vía script Lua en Redis (sliding
window). Fail-open si Redis falla (rate_limiter.py:62-68).

6.2 Costos / tokens — HALLAZGO IMPORTANTE

- num_ctx por defecto = None (ollama_llm_facade_settings.py:27) → Ollama usa su
ventana por defecto (frecuentemente 2.048–4.096 tokens según modelo). Con
max_context_chars=10.000 (~2.500–3.300 tokens) + system prompt + historial +
few-shots, el prompt puede exceder la ventana y ser truncado silenciosamente por
Ollama desde el inicio del contexto → pérdida invisible de instrucciones o contexto.
No hay conteo de tokens en ningún punto; todos los presupuestos son en caracteres.
- Sin gestión de costos: no se cuentan tokens de entrada/salida, no hay métricas de
tokens ni de coste por etapa. (Mitigado parcialmente porque el LLM es
local/self-hosted.)
- Llamadas redundantes/caras: una sola consulta de chat-RAG puede disparar 5–10+
invocaciones LLM secuenciales (reformulación×2, reducción×N pasadas, análisis,
síntesis, guardrail, redacción). Impacto directo en latencia.

6.3 Latencia

- Operaciones bloqueantes: todo el pipeline es secuencial. No se paralelizan:
graph-retrieval + vector-retrieval; ni reformulación base + keywords.
- Esperas innecesarias: la reducción de contexto multi-pasada puede añadir varias
llamadas LLM antes de la primera respuesta visible.

---
FASE 7 — AUDITORÍA DE SEGURIDAD

Vector: Prompt injection (usuario)
Estado: Mitigado por NeMo self_check_input + cláusula "DATOS no instrucciones".
Bypasseable.
Severidad: Media
────────────────────────────────────────
Vector: Prompt injection (operador system_prompt)
Estado: Solo precedencia textual; sin defensa estructural.
Severidad: Media
────────────────────────────────────────
Vector: Context/document poisoning
Estado: Contexto recuperado se inyecta como texto; guardrail de salida falla-abierto.
Severidad: Alta
────────────────────────────────────────
Vector: Output guardrail fail-open
Estado: GuardrailsNode.process aprueba ante cualquier excepción
(guardrails_node.py:61-63) y ante resultado no parseable (:124-125). Una saturación
del LLM desactiva el control de seguridad de salida.
Severidad: Alta
────────────────────────────────────────
Vector: Multi-tenant / IDOR
Estado: Aislamiento delegado 100% al downstream vía JWT reenviado. chat_id y
document_ids no se validan como pertenecientes al usuario en este servicio. Si el
downstream no valida, hay riesgo de acceso cruzado.
Severidad: Alta (verificar downstream)
────────────────────────────────────────
Vector: Data leakage por logs
Estado: log_payloads (default False) registra prompts, fragmentos y respuestas
completas a nivel INFO (document_context_provider.py:236-254,
llm_payload_logging.py). Riesgo de PII si se activa en prod.
Severidad: Media
────────────────────────────────────────
Vector: Data leakage por tracing
Estado: record_retrieved_documents envía contenido completo de fragmentos como
atributos de span a Phoenix (tracing.py:141-158).
Severidad: Media (si tracing activo)
────────────────────────────────────────
Vector: Exposición de prompts internos
Estado: system prompts estáticos; bloqueo de "mostrar instrucciones" por NeMo.
Severidad: Baja
────────────────────────────────────────
Vector: Escalada de privilegios
Estado: RBAC por permiso (Authorizer.require_permissions) en cada controller.
Correcto.
Severidad: Baja
────────────────────────────────────────
Vector: Fail-open acumulado
Estado: rate-limit, guardrail input (config fail_open), guardrail output →
disponibilidad sobre seguridad. Decisión consciente pero debe documentarse.
Severidad: Media
────────────────────────────────────────
Vector: Validación de entrada
Estado: Fuerte: Message sanitiza chars de control, límites de longitud, frozen DTOs,
body-size middleware.
Severidad: Baja (positivo)
────────────────────────────────────────
Vector: Determinismo del clasificador
Estado: guardrail/redacción usan get_llm_base() con temperature=0.3 y seed=None →
veredictos de seguridad no deterministas.
Severidad: Baja

---
FASE 8 — AUDITORÍA DE OBSERVABILIDAD

8.1 Logging

- Registrado: eventos por etapa con extra estructurado (user_id, error_type, counts),
request_id/X-Request-ID propagado a llamadas downstream (http_client.py:180-182). JSON
logging vía python-json-logger.
- Falta: conteo de tokens, coste, scores de retrieval/rerank, latencia por etapa/nodo,
métrica de fragmentos descartados por truncado. Los logs de error usan exc_info pero
a menudo omiten el detalle del mensaje (solo error_type) → dificulta el diagnóstico.

8.2 Métricas

- Presente: Prometheus (prometheus-fastapi-instrumentator) →
latencia/throughput/in-progress a nivel HTTP.
- Ausente: métricas de dominio LLM — tokens, coste, tasa de fallback, tasa de rechazo
de guardrails, hits/miss de cache de auth, profundidad de reducción de contexto,
latencia LLM vs retrieval.

8.3 Trazabilidad

- Phoenix/OpenInference opcional (tracing.py): spans CHAIN y RETRIEVER con
input/output y documentos. Bueno cuando TRACING_ENABLED. Por defecto desactivado.
- ¿Reconstrucción completa de una conversación? Parcial. Con tracing activo +
log_payloads se reconstruye una invocación, pero como no hay persistencia de
conversación ni un trace-id de conversación, no se puede reconstruir un hilo
multi-turno de extremo a extremo desde el servicio mismo.

---
FASE 9 — MATRIZ DE HALLAZGOS

ID: F-01
Categoría: Tokens/Contexto
Archivo / Ubicación: ollama_llm_facade_settings.py:27
Evidencia: num_ctx: Optional[int] = None + presupuestos solo en chars
Impacto: Truncado silencioso del prompt por Ollama; pérdida de instrucciones/contexto
Severidad: Crítico
Recomendación (alto nivel): Fijar num_ctx explícito acorde al modelo y al presupuesto;

medir tokens reales
────────────────────────────────────────
ID: F-02
Categoría: Seguridad
Archivo / Ubicación: guardrails_node.py:61-63,124-125
Evidencia: Fail-open ante excepción y ante salida no parseable
Impacto: Control de seguridad de salida se desactiva bajo carga/fallo
Severidad: Alto
Recomendación (alto nivel): Política fail-closed configurable para el guardrail de
salida
────────────────────────────────────────
ID: F-03
Categoría: Multi-tenant
Archivo / Ubicación: context_retriever_node.py, document_fetcher_node.py,
*_provider._build_headers
Evidencia: chat_id/document_ids reenviados sin validar pertenencia en este servicio
Impacto: Posible acceso cruzado si downstream no valida
Severidad: Alto
Recomendación (alto nivel): Confirmar/forzar validación de ownership; no confiar solo
en JWT downstream
────────────────────────────────────────
ID: F-04
Categoría: RAG/Contexto
Archivo / Ubicación: context_formatting.py:36, generation_messages.py:13-21
Evidencia: content[:remaining] corta a mitad de palabra sin marcador
Impacto: Pérdida de info, citas incompletas
Severidad: Medio
Recomendación (alto nivel): Recorte por límites de oración + marcador de truncado
────────────────────────────────────────
ID: F-05
Categoría: Streaming/UX
Archivo / Ubicación: answer_synthesizer_node.py:93; rag_agent_workflow.py:101-120
Evidencia: Síntesis con ainvoke, no astream
Impacto: El agente RAG no streamea tokens; alta percepción de latencia
Severidad: Medio
Recomendación (alto nivel): Token-streaming en el nodo de síntesis
────────────────────────────────────────
ID: F-06
Categoría: Latencia/Costo
Archivo / Ubicación: general_chat_service.py:104-109, context_reduction_processor.py
Evidencia: 5–10+ llamadas LLM secuenciales por request
Impacto: Latencia y coste elevados
Severidad: Medio
Recomendación (alto nivel): Paralelizar etapas independientes; cachear reformulaciones
────────────────────────────────────────
ID: F-07
Categoría: Observabilidad
Archivo / Ubicación: tracing.py, ausencia de métricas de tokens
Evidencia: Solo métricas HTTP; sin tokens/coste/scores
Impacto: Imposible monitorear coste y calidad RAG
Severidad: Medio
Recomendación (alto nivel): Métricas de dominio LLM (tokens, fallback, rechazo
guardrail, latencia por etapa)
────────────────────────────────────────
ID: F-08
Categoría: Integridad conversación
Archivo / Ubicación: rag_agent_state_builder.py:51
Evidencia: Mensajes assistant del cliente confiados
Impacto: History poisoning
Severidad: Medio
Recomendación (alto nivel): Tratar turnos del asistente provistos por cliente con
desconfianza/validación
────────────────────────────────────────
ID: F-09
Categoría: Data leakage
Archivo / Ubicación: document_context_provider.py:236-254; tracing.py:141-158
Evidencia: Logging/tracing de contenido completo
Impacto: Exposición de datos sensibles si se habilita
Severidad: Medio
Recomendación (alto nivel): Redacción/sampling; prohibir log_payloads en prod
────────────────────────────────────────
ID: F-10
Categoría: Prompts
Archivo / Ubicación: múltiples *_prompt.py / *_settings.py
Evidencia: Sin versionado; cláusulas de seguridad duplicadas
Impacto: Mantenibilidad y deriva de políticas
Severidad: Medio
Recomendación (alto nivel): Registro central de prompts con versión + bloques
reutilizables
────────────────────────────────────────
ID: F-11
Categoría: Inyección operador
Archivo / Ubicación: prompt_augmentation.py:1-18
Evidencia: Precedencia solo textual
Impacto: Operador puede intentar override de reglas
Severidad: Medio
Recomendación (alto nivel): Separación estructural / validación del prompt de operador
────────────────────────────────────────
ID: F-12
Categoría: Inferencia
Archivo / Ubicación: ollama_llm_facade_settings.py:30
Evidencia: request_timeout=600s
Impacto: Conexiones colgadas largas en endpoint interactivo
Severidad: Bajo
Recomendación (alto nivel): Timeout interactivo más bajo; presupuesto por tipo de
tarea
────────────────────────────────────────
ID: F-13
Categoría: Determinismo
Archivo / Ubicación: guardrails_node, *_reduction usan get_llm_base() (temp 0.3)
Evidencia: Clasificación/seguridad con temperatura
Impacto: Veredictos no deterministas
Severidad: Bajo
Recomendación (alto nivel): temperature=0, seed fijo para tareas de clasificación
────────────────────────────────────────
ID: F-14
Categoría: Robustez
Archivo / Ubicación: request_token.py + BaseHTTPMiddleware
Evidencia: JWT propagado por contextvar a través de BaseHTTPMiddleware
Impacto: Acoplamiento frágil a la propagación de contextvars
Severidad: Bajo (verificar)
Recomendación (alto nivel): Tests de integración que aseguren reenvío del JWT
────────────────────────────────────────
ID: F-15
Categoría: Tool calling
Archivo / Ubicación: dependencies.py:104 (sin tool_factories); ollama_tool_manager.py
Evidencia: Infra de tools completa pero nunca registrada
Impacto: Código muerto / capacidad inexistente
Severidad: Informativo
Recomendación (alto nivel): Eliminar o documentar como extensión futura

---
FASE 10 — EVALUACIÓN FINAL

▎ Puntuaciones justificadas con evidencia inspeccionada. Escala 0–100.

Dimensión: Arquitectura de IA
Puntaje: 78
Justificación basada en evidencia: Separación de capas limpia, 3 motores bien
delimitados, LangGraph con routing por intent, degradación grácil en casi todos los
nodos. Resta: pipeline 100% secuencial, tool-calling muerto (F-15), acoplamiento por

inyección manual.
────────────────────────────────────────
Dimensión: Calidad del sistema RAG
Puntaje: 68
Justificación basada en evidencia: Híbrido semántico+BM25+rerank+adjacent, agrupación
por documento, reducción map-reduce sólida. Resta: truncado destructivo (F-04), sin
dedup semántica, sin conteo de tokens (F-01), sin verificación de citas.
────────────────────────────────────────
Dimensión: Seguridad
Puntaje: 58
Justificación basada en evidencia: Buena base: RBAC por permiso, sanitización de
input,
NeMo input filter, body-size limit, validación estricta de DTOs. Resta grave:
guardrail de salida fail-open (F-02), aislamiento multi-tenant no verificado
localmente (F-03), inyección de operador (F-11), history poisoning (F-08).
────────────────────────────────────────
Dimensión: Escalabilidad
Puntaje: 70
Justificación basada en evidencia: Stateless por conversación (escala horizontal
fácil), singletons sin estado mutable compartido, rate-limit distribuido en Redis,
circuit breaker HTTP. Resta: coste de latencia por múltiples LLM secuenciales
(F-06),
sin backpressure de cola de inferencia.
────────────────────────────────────────
Dimensión: Observabilidad
Puntaje: 55
Justificación basada en evidencia: request_id propagado, logging estructurado,
Prometheus HTTP, tracing Phoenix opcional. Resta: cero métricas de
tokens/coste/calidad RAG (F-07), tracing apagado por defecto, sin trace de
conversación multi-turno.
────────────────────────────────────────
Dimensión: Streaming
Puntaje: 72
Justificación basada en evidencia: SSE robusto: heartbeat, cancelación limpia, límite
de tamaño, retry solo en establecimiento. Resta: el agente RAG no streamea tokens
(F-05).
────────────────────────────────────────
Dimensión: Gestión de prompts
Puntaje: 52
Justificación basada en evidencia: Prompts claros y con few-shots; override por
settings. Resta: sin versionado, duplicación de políticas, hardcoding masivo,
defaults dentro de propiedades de settings (F-10).
────────────────────────────────────────
Dimensión: Mantenibilidad
Puntaje: 74
Justificación basada en evidencia: Código consistente, interfaces explícitas, DTOs
frozen, manejo de excepciones tipado, tests presentes (test/unit, test/api). Resta:
duplicación de prompts, ramas de fail-open dispersas, código muerto.
────────────────────────────────────────
Dimensión: Preparación para producción
Puntaje: 63
Justificación basada en evidencia: Arranque con probe + rollback de dependencias,
circuit breakers, rate-limit, guardrails. Resta: F-01 (riesgo de truncado),
F-02/F-03
(seguridad), falta de métricas de coste/tokens, timeout 600s.

Veredicto global

Sistema bien estructurado a nivel de ingeniería (manejo de errores, resiliencia HTTP,
validación, SSE) pero con brechas específicas de plataforma de inferencia: gestión de
tokens basada solo en caracteres con num_ctx sin fijar (F-01, la más crítica), un
guardrail de salida que se desactiva bajo fallo (F-02), aislamiento multi-tenant no
verificable dentro del propio servicio (F-03), y ausencia de observabilidad de
coste/tokens. Antes de un despliegue empresarial de alto volumen, priorizar F-01, F-02
y F-03.

---