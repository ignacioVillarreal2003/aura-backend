from app.application.exceptions.app_exception import AppException


class DocumentIngestionServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DocumentIngestionServiceReadException(DocumentIngestionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DocumentIngestionServiceCleanException(DocumentIngestionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DocumentIngestionServiceSplitException(DocumentIngestionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DocumentIngestionServiceEmbedException(DocumentIngestionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DocumentIngestionServicePersistenceException(DocumentIngestionServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
