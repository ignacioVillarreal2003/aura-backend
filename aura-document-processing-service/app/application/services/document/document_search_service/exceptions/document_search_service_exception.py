from app.application.exceptions.app_exception import AppException


class DocumentSearchServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DocumentSearchInvalidRequestException(DocumentSearchServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class DocumentSearchEmbeddingException(DocumentSearchServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentSearchRetrievalException(DocumentSearchServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
