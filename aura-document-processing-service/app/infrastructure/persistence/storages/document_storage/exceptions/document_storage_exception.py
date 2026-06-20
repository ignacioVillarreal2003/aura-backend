from app.application.exceptions.app_exception import AppException


class DocumentStorageException(AppException):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code)


class DocumentValidationException(DocumentStorageException):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message, status_code=status_code)


class DocumentExtensionException(DocumentValidationException):
    pass


class DocumentSizeLimitException(DocumentValidationException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=413)


class DocumentUploadException(DocumentStorageException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentDownloadException(DocumentStorageException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentDeleteException(DocumentStorageException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentNotFoundException(DocumentStorageException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)
