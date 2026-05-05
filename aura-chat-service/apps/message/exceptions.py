from core.exceptions import ConflictException, ForbiddenException, ServiceUnavailableException


class ChatAiReplyInProgressException(ConflictException):
    """Another message is being processed; wait for the assistant to finish."""

    error_code = "chat_ai_reply_in_progress"
    detail = "Wait until the assistant finishes the current reply."


class MessageAccessDeniedException(ForbiddenException):
    error_code = "message_access_denied"
    detail = "You do not have access to messages in this chat"


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "AI service is temporarily unavailable"


class TranscriptionException(ServiceUnavailableException):
    status_code = 502
    error_code = "transcription_error"
    detail = "Audio could not be transcribed"
