from app.application.exceptions.app_exception import AppException


class PostProcessDocumentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class PostProcessAlreadyRunningException(PostProcessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class PostProcessNotRunningException(PostProcessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PostProcessDocumentFailedException(PostProcessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class PostProcessDocumentUnauthorizedException(PostProcessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class PostProcessDocumentInvalidRequestException(PostProcessDocumentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
