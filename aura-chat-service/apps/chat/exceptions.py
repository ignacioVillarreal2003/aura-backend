from core.exceptions import ForbiddenException, NotFoundException, ValidationException


class ChatNotFoundException(NotFoundException):
    error_code = "chat_not_found"
    detail = "Chat not found"


class ChatAccessDeniedException(ForbiddenException):
    error_code = "chat_access_denied"
    detail = "You do not have access to this chat"


class ShareLinkNotFoundException(NotFoundException):
    error_code = "share_link_not_found"
    detail = "Share link not found"


class ShareLinkExpiredOrInactiveException(ValidationException):
    error_code = "share_link_expired_or_inactive"
    detail = "This share link is expired or inactive"


class WebhookNotFoundException(NotFoundException):
    error_code = "webhook_not_found"
    detail = "Webhook not found"
