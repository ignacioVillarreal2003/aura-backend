from core.exceptions import ConflictException, ForbiddenException, NotFoundException, ServiceException, \
    ServiceUnavailableException, ValidationException


class ExportTooLargeException(ServiceException):
    status_code = 413
    error_code = "export_too_large"
    detail = "Chat exceeds the maximum message count allowed for export"


class ChatAiReplyInProgressException(ConflictException):
    error_code = "chat_ai_reply_in_progress"
    detail = "Wait until the assistant finishes the current reply."


class MessageAccessDeniedException(ForbiddenException):
    error_code = "message_access_denied"
    detail = "You do not have access to messages in this chat"


class LLMServiceException(ServiceUnavailableException):
    status_code = 502
    error_code = "llm_service_error"
    detail = "AI service is temporarily unavailable"


class MessageNotFoundException(NotFoundException):
    error_code = "message_not_found"
    detail = "Message not found"


class PDFGenerationException(ServiceException):
    status_code = 500
    error_code = "pdf_generation_error"
    detail = "Failed to generate PDF"


class NotChatCreatorException(ForbiddenException):
    error_code = "not_chat_creator"
    detail = "Only the chat creator can perform this action"


class NotAIMessageException(ValidationException):
    error_code = "not_ai_message"
    detail = "Feedback can only be submitted for AI messages"


class ReaderCannotSendMessageException(ForbiddenException):
    error_code = "reader_cannot_send_message"
    detail = "Readers cannot send messages in this chat"


class ChatLockedException(ForbiddenException):
    error_code = "chat_locked"
    detail = "This chat is locked and does not accept new messages"


class MessageDeleteForbiddenException(ForbiddenException):
    error_code = "message_delete_forbidden"
    detail = "Only a chat owner can delete messages"


class NotChatOwnerException(ForbiddenException):
    error_code = "not_chat_owner"
    detail = "Only a chat owner can perform this action"
