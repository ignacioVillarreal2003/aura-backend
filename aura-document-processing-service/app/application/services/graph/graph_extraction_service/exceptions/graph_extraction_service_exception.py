from app.application.exceptions.app_exception import AppException


class GraphExtractionServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class GraphExtractionAlreadyRunningException(GraphExtractionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class GraphExtractionDocumentNotFoundException(GraphExtractionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)
