from core.exceptions import ForbiddenException, NotFoundException


class PeerMessageNotFoundException(NotFoundException):
    error_code = "peer_message_not_found"
    detail = "Peer message not found"


class PeerChatAccessDeniedException(ForbiddenException):
    error_code = "peer_chat_access_denied"
    detail = "You do not have access to this chat"


class PeerMessageForbiddenException(ForbiddenException):
    error_code = "peer_message_forbidden"
    detail = "You cannot modify this message"
