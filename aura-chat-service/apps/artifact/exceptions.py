from core.exceptions.base import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)


class ArtifactNotFoundException(NotFoundException):
    error_code = "artifact_not_found"
    detail = "Artefacto no encontrado."


class ArtifactAccessDeniedException(ForbiddenException):
    error_code = "artifact_access_denied"
    detail = "No tenés acceso a este artefacto."


class UnknownArtifactTypeException(ValidationException):
    error_code = "artifact_unknown_type"
    detail = "Tipo de artefacto desconocido."
