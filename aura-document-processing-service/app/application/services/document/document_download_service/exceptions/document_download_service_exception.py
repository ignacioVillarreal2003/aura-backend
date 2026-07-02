from app.application.exceptions.app_exception import AppException


class DocumentDownloadServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class DocumentDownloadNotFoundException(DocumentDownloadServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class DocumentDownloadInvalidRequestException(DocumentDownloadServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class DocumentDownloadStorageException(DocumentDownloadServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DocumentDownloadNotReadyException(DocumentDownloadServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)
