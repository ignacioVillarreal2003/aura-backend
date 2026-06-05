from core.exceptions.base import (
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
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


class ArtifactCreationFailedException(ServiceUnavailableException):
    status_code = 502
    error_code = "artifact_creation_failed"
    detail = "No se pudo crear el encabezado del artefacto."


class TranscriptionException(ServiceUnavailableException):
    status_code = 502
    error_code = "transcription_error"
    detail = "Audio could not be transcribed"


class TranscriptionBusyException(ServiceUnavailableException):
    status_code = 503
    error_code = "transcription_busy"
    detail = "Transcription service is at capacity; please retry shortly"
