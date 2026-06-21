from app.application.exceptions.app_exception import AppException


class ReprocessDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class ReprocessDocumentNotFoundException(ReprocessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)
