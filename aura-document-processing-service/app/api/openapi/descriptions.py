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
            "name": "create-document",
            "description": "Alta de documentos por multipart con límite estricto.",
        },
        {
            "name": "delete-document",
            "description": "Borrado lógico por documento o por chat.",
        },
        {
            "name": "document-query",
            "description": "Consulta y listado de documentos.",
        },
        {
            "name": "document-download",
            "description": "Descarga de archivos de documentos.",
        },
        {
            "name": "fragment-query",
            "description": "Consulta de fragmentos de contexto.",
        },
        {
            "name": "post-process-document",
            "description": "Inicio, estado y detención del postproceso de documentos.",
        },
        {
            "name": "post-process-fragment",
            "description": "Inicio, estado y detención del postproceso de fragmentos.",
        },
    ]


def root_api_description() -> str:
    return f"""## API de procesamiento de documentos
        {API_ROOT_NOTE}
        {AUTH_BEARER_NOTE}
        Errores comunes: 401, 403, 404, 422, 429 y 500.
    """
