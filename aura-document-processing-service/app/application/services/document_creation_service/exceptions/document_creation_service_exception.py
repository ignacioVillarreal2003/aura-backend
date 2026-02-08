from starlette import status

from app.application.exceptions.app_exception import AppException


class UnsupportedDocumentTypeError(AppException):
    def __init__(
            self,
            message: str = "The type of the document is not supported"
    ):
        super().__init__(
            message,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE
        )
