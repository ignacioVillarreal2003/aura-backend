from starlette import status

from app.application.exceptions.app_exception import AppError


class DocumentNotFoundError(AppError):
    def __init__(
            self,
            message: str = "Document not found"
    ):
        super().__init__(
            message,
            status_code=status.HTTP_404_NOT_FOUND
        )
