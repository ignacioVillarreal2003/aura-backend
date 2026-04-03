from app.application.exceptions.app_exception import AppException


class DeleteDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DeleteDocumentNotFoundException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class DeleteDocumentUnauthorizedException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class DeleteDocumentFailedException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DeleteFragmentsFailedException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DeleteDocumentStorageException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class DeleteDocumentInvalidRequestException(DeleteDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
