from app.application.exceptions.app_exception import AppException


class UpdateDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class UpdateDocumentNotFoundException(UpdateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class UpdateDocumentUnauthorizedException(UpdateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class UpdateDocumentInvalidRequestException(UpdateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class UpdateDocumentFailedException(UpdateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
