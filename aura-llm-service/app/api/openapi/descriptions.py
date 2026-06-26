API_ROOT_NOTE = (
    "Rutas de negocio bajo **`/api/v1`**. Documentación en `/api/docs` y esquema en `/api/openapi.json`."
)

AUTH_BEARER_NOTE = (
    "La mayoría de rutas requiere `Authorization: Bearer <token>`. Las respuestas pueden incluir `X-Request-ID`."
)


def openapi_tags_metadata() -> list[dict[str, str]]:
    return [
        {
            "name": "health",
            "description": "Estado de vida y preparación del servicio.",
        },
        {
            "name": "document-question",
            "description": "Preguntas sobre documentos (JSON y stream SSE).",
        },
        {
            "name": "document-summary",
            "description": "Resúmenes de documentos.",
        },
        {
            "name": "document-action",
            "description": "Acciones estructuradas sobre documentos.",
        },
        {
            "name": "document-classify",
            "description": "Clasificación de documentos.",
        },
        {
            "name": "fragment-contextualize",
            "description": "Contextualización de fragmentos (Contextual Retrieval).",
        },
        {
            "name": "rag-agent",
            "description": "Agente RAG con herramientas (JSON y stream SSE).",
        },
        {
            "name": "graph-extraction",
            "description": "Extracción de entidades y relaciones para el grafo de conocimiento.",
        },
        {
            "name": "graph-query-translation",
            "description": "Traducción de preguntas en lenguaje natural a intents estructurados sobre el grafo.",
        },
        {
            "name": "general-chat",
            "description": "Chat de propósito general con el asistente (sin RAG).",
        },
        {
            "name": "report",
            "description": "Generación de informes a partir de documentos.",
        },
        {
            "name": "checklist",
            "description": "Generación de checklists a partir de documentos.",
        },
        {
            "name": "timeline",
            "description": "Generación de líneas de tiempo a partir de documentos.",
        },
        {
            "name": "quiz",
            "description": "Generación de cuestionarios a partir de documentos.",
        },
        {
            "name": "lessons-learned",
            "description": "Generación de lecciones aprendidas a partir de documentos.",
        },
        {
            "name": "decision-brief",
            "description": "Generación de informes de decisión a partir de documentos.",
        },
    ]


def root_api_description() -> str:
    return f"""## API de LLM \n{API_ROOT_NOTE}\n{AUTH_BEARER_NOTE}"""
