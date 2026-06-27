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
            "name": "bulk-create-document",
            "description": "Alta de varios documentos en una sola solicitud multipart.",
        },
        {
            "name": "update-document",
            "description": "Actualización parcial (PATCH) de la metadata editable de un documento.",
        },
        {
            "name": "delete-document",
            "description": "Borrado lógico por documento o por chat.",
        },
        {
            "name": "restore-document",
            "description": "Restauración de documentos eliminados de forma lógica.",
        },
        {
            "name": "document-query",
            "description": "Consulta, estado y listado de documentos.",
        },
        {
            "name": "document-download",
            "description": "Descarga de archivos de documentos.",
        },
        {
            "name": "document-search",
            "description": "Búsqueda de documentos por similitud de contenido (vectorial).",
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
        {
            "name": "graph-query",
            "description": "Consulta el grafo de conocimiento traduciendo lenguaje natural a Cypher parametrizado.",
        },
        {
            "name": "graph-entity",
            "description": "Lookup de entidades del grafo y sus relaciones directas.",
        },
        {
            "name": "graph-path",
            "description": "Caminos (más corto / todos) entre entidades del grafo.",
        },
    ]


def root_api_description() -> str:
    return f"""## API de procesamiento de documentos \n{API_ROOT_NOTE}\n{AUTH_BEARER_NOTE}"""
