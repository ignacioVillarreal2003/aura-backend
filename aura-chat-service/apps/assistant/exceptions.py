from core.exceptions.base import ForbiddenException, NotFoundException


class AssistantNotFoundException(NotFoundException):
    error_code = "assistant_not_found"
    detail = "Asistente no encontrado."


class AssistantAccessDeniedException(ForbiddenException):
    error_code = "assistant_access_denied"
    detail = "No tenés acceso a este asistente."


class AssistantInactiveException(NotFoundException):
    error_code = "assistant_inactive"
    detail = "El asistente no está disponible actualmente."
