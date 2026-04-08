from typing import Optional, Any


class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        details: Optional[Any] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message=message, code=code, status_code=404)


class ConversationNotFoundError(NotFoundError):
    """Conversation not found error."""
    
    def __init__(self, conversation_id: str = ""):
        message = f"Conversation not found"
        if conversation_id:
            message = f"Conversation {conversation_id} not found"
        super().__init__(message=message, code="CONVERSATION_NOT_FOUND")


class MessageNotFoundError(NotFoundError):
    """Message not found error."""
    
    def __init__(self, message_id: str = ""):
        message = f"Message not found"
        if message_id:
            message = f"Message {message_id} not found"
        super().__init__(message=message, code="MESSAGE_NOT_FOUND")


class ToolCallNotFoundError(NotFoundError):
    """Tool call not found error."""
    
    def __init__(self, tool_call_id: str = ""):
        message = f"Tool call not found"
        if tool_call_id:
            message = f"Tool call {tool_call_id} not found"
        super().__init__(message=message, code="TOOL_CALL_NOT_FOUND")


class ForbiddenError(AppError):
    """Access denied error."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="ACCESS_DENIED",
            status_code=403
        )


class UnauthorizedError(AppError):
    """Authentication error."""
    
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
            status_code=401
        )


class ValidationError(AppError):
    """Validation error."""
    
    def __init__(self, message: str = "Validation failed", details: Any = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )


class RateLimitError(AppError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str = "Too many requests, please try again later"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )


class LLMError(AppError):
    """Error communicating with LLM service."""
    
    def __init__(self, message: str = "Error communicating with LLM service"):
        super().__init__(
            message=message,
            code="LLM_ERROR",
            status_code=502
        )


class StreamingError(AppError):
    """Error during response streaming."""
    
    def __init__(self, message: str = "Error during response streaming"):
        super().__init__(
            message=message,
            code="STREAMING_ERROR",
            status_code=500
        )


class ConversationDeletedError(AppError):
    """Conversation has been deleted."""
    
    def __init__(self):
        super().__init__(
            message="This conversation has been deleted",
            code="CONVERSATION_DELETED",
            status_code=410
        )


