from core.exceptions import ForbiddenException, ServiceException


class MessageSendException(ServiceException):
    status_code = 500
    error_code = "message_send_error"
    detail = "Failed to send message"


class MessageAccessDeniedException(ForbiddenException):
    error_code = "message_access_denied"
    detail = "You do not have access to messages in this chat"


class LLMServiceException(ServiceException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "AI service is temporarily unavailable"
