from app.application.exceptions.app_exception import AppException


class FragmentQueryServiceException(AppException):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message, status_code=status_code)


class FragmentQueryNotFoundException(FragmentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class FragmentQueryInvalidRequestException(FragmentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class FragmentQueryEmbeddingException(FragmentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class FragmentQueryRetrievalException(FragmentQueryServiceException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
