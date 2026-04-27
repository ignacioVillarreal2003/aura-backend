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
            "name": "agent",
            "description": "Agente con herramientas.",
        },
        {
            "name": "document-classify",
            "description": "Clasificación de documentos.",
        },
        {
            "name": "fragment-enrich",
            "description": "Enriquecimiento de fragmentos.",
        },
    ]


def root_api_description() -> str:
    return f"""## API de LLM \n{API_ROOT_NOTE}\n{AUTH_BEARER_NOTE}"""
