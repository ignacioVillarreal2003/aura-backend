from app.application.exceptions.app_exception import AppException


class CreateDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class CreateDocumentValidationException(CreateDocumentServiceException):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message, status_code=status_code)


class CreateDocumentUploadException(CreateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class CreateDocumentPersistenceException(CreateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class CreateDocumentUnauthorizedException(CreateDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class CreateDocumentUnsupportedTypeException(CreateDocumentValidationException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415)


class CreateDocumentSizeExceededException(CreateDocumentValidationException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413)


class CreateDocumentInvalidException(CreateDocumentValidationException):
    pass
