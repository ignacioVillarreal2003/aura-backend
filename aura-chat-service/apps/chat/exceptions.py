from core.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException


class ChatNotFoundException(NotFoundException):
    error_code = "chat_not_found"
    detail = "Chat not found"


class ChatAccessDeniedException(ForbiddenException):
    error_code = "chat_access_denied"
    detail = "You do not have access to this chat"


class ChatAiReplyInProgressException(ConflictException):
    error_code = "chat_ai_reply_in_progress"
    detail = "Wait until the assistant finishes the current reply."


class ShareLinkNotFoundException(NotFoundException):
    error_code = "share_link_not_found"
    detail = "Share link not found"


class ShareLinkExpiredOrInactiveException(ValidationException):
    error_code = "share_link_expired_or_inactive"
    detail = "This share link is expired or inactive"
