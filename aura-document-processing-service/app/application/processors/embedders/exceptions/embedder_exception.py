from app.application.exceptions.app_exception import AppException


class EmbedderException(AppException):
    pass


class UnsupportedEmbedderTypeException(EmbedderException):
    def __init__(self, embedder_type: str):
        super().__init__(
            f"Unsupported embedder type: '{embedder_type}'",
            status_code=422
        )


class EmbedderInitializationException(EmbedderException):
    def __init__(self, embedder_name: str, cause: Exception):
        super().__init__(
            f"Failed to initialize embedder '{embedder_name}': {cause}",
            status_code=500
        )


class EmbedDocumentsException(EmbedderException):
    def __init__(self, embedder_name: str, cause: Exception):
        super().__init__(
            f"Failed to generate document embeddings with '{embedder_name}': {cause}",
            status_code=500
        )


class EmbedQueryException(EmbedderException):
    def __init__(self, embedder_name: str, cause: Exception):
        super().__init__(
            f"Failed to generate query embedding with '{embedder_name}': {cause}",
            status_code=500
        )
