from app.application.exceptions.app_exception import AppException


class LessonsLearnedServiceException(AppException):
    def __init__(
            self,
            message: str,
            status_code: int = 500,
            *,
            code: str | None = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, code=code)
