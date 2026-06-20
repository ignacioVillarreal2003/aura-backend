from app.application.exceptions.app_exception import AppException


class RestoreDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class RestoreDocumentNotFoundException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class RestoreDocumentUnauthorizedException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class RestoreDocumentInvalidRequestException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class RestoreDocumentConflictException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class RestoreDocumentFailedException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class RestoreFragmentsFailedException(RestoreDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
