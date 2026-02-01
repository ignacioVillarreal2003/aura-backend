from app.application.exceptions.app_exception import AppError


class DatabaseError(AppError):
    def __init__(self, message: str = "Error en la base de datos", *, code: str | None = None):
        super().__init__(message, status_code=500, code=code)
