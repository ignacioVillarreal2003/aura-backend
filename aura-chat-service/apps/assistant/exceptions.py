from core.exceptions.base import ConflictException, ForbiddenException, NotFoundException, ValidationException


class AssistantNotFoundException(NotFoundException):
    error_code = "assistant_not_found"
    detail = "Asistente no encontrado."


class AssistantAccessDeniedException(ForbiddenException):
    error_code = "assistant_access_denied"
    detail = "No tenés acceso a este asistente."


class AssistantInactiveException(ValidationException):
    error_code = "assistant_inactive"
    detail = "El asistente no está disponible actualmente."


class AssistantAlreadyExistsException(ConflictException):
    error_code = "assistant_already_exists"
    detail = "Ya existe un asistente con ese nombre."
