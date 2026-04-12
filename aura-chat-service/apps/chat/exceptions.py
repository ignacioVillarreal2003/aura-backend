from core.exceptions import ForbiddenException, NotFoundException


class ChatNotFoundException(NotFoundException):
    error_code = "chat_not_found"
    detail = "Chat not found"


class ChatAccessDeniedException(ForbiddenException):
    error_code = "chat_access_denied"
    detail = "You do not have access to this chat"
