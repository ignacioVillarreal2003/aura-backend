from app.application.exceptions.app_exception import AppException


class BulkCreateDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class BulkCreateDocumentValidationException(BulkCreateDocumentServiceException):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message, status_code=status_code)
