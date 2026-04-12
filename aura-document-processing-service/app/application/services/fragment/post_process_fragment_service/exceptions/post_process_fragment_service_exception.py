from app.application.exceptions.app_exception import AppException


class PostProcessFragmentServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class PostProcessFragmentAlreadyRunningException(PostProcessFragmentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class PostProcessFragmentNotRunningException(PostProcessFragmentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PostProcessFragmentFailedException(PostProcessFragmentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class PostProcessFragmentUnauthorizedException(PostProcessFragmentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=403)


class PostProcessFragmentInvalidRequestException(PostProcessFragmentServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
