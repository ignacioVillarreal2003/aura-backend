from app.application.exceptions.app_exception import AppException


class DatabaseError(AppException):
    def __init__(
            self,
            message: str = "Database error",
            *,
            code: str | None = None
    ):
        super().__init__(
            message,
            status_code=500,
            code=code
        )
