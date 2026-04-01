from app.application.exceptions.app_exception import AppException


class DocumentClassifyServiceException(AppException):
    def __init__(
            self,
            message: str,
            status_code: int = 502,
            *,
            code: str | None = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, code=code)
