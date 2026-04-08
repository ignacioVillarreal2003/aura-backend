from app.application.exceptions.app_exception import AppException


class DocumentQueryServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DocumentQueryNotFoundException(DocumentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class DocumentQueryUnauthorizedException(DocumentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class DocumentQueryInvalidRequestException(DocumentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class DocumentQueryEmbeddingException(DocumentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentQueryFragmentRetrievalException(DocumentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
