from app.application.exceptions.app_exceptions import AppError


class FragmentRetrievalServiceError(AppError):
    def __init__(self,
                 message: str = "Error in fragment retrieval service",
                 *,
                 code: str | None = None):
        super().__init__(
            message,
            status_code=500,
            code=code,
        )
