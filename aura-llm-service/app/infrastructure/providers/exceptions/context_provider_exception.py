from app.application.exceptions.app_exceptions import AppError


class ContextProviderError(AppError):
    def __init__(self,
                 message: str = "Context provider operation failed",
                 *,
                 status_code: int = 500,
                 code: str | None = None):
        super().__init__(
            message=message,
            status_code=status_code,
            code=code,
        )


class ContextRetrievalByQuestionError(ContextProviderError):
    def __init__(self,
                 message: str = "Failed to retrieve context based on the provided question",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )


class ContextRetrievalByDocumentError(ContextProviderError):
    def __init__(self,
                 message: str = "Failed to retrieve context for the specified document",
                 *,
                 code: str | None = None):
        super().__init__(
            message=message,
            code=code
        )
