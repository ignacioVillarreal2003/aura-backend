import logging
from typing import Optional

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.general.document_question_service.steps.validate_request.validate_request_settings import (
    ValidateRequestSettings,
)

logger = logging.getLogger(__name__)


class ValidateRequestPlugin(DocumentQuestionPlugin):
    def __init__(self, validate_request_settings: Optional[ValidateRequestSettings] = None) -> None:
        self._settings = validate_request_settings or ValidateRequestSettings()

    @property
    def plugin_name(self) -> str:
        return "validate_request"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        logger.debug("Starting request validation")

        if not state.messages:
            raise RequestValidationException(
                "Debe enviar al menos un mensaje con la consulta actual.",
                status_code=400,
            )

        question = state.current_message.content
        if not question or not question.strip():
            logger.warning("Question validation failed: empty or whitespace-only")
            raise RequestValidationException(
                "La pregunta no puede estar vacía.",
                status_code=400,
            )

        question_length = len(question.strip())
        if question_length < self._settings.min_question_length:
            logger.warning(
                "Question too short",
                extra={"length": question_length, "min": self._settings.min_question_length},
            )
            raise RequestValidationException(
                f"La pregunta es demasiado corta. Debe tener al menos "
                f"{self._settings.min_question_length} caracteres.",
                status_code=400,
            )

        if question_length > self._settings.max_question_length:
            logger.warning(
                "Question too long",
                extra={"length": question_length, "max": self._settings.max_question_length},
            )
            raise RequestValidationException(
                f"La pregunta es demasiado larga. No debe exceder "
                f"{self._settings.max_question_length} caracteres.",
                status_code=400,
            )

        history_count = len(state.history_messages)
        if history_count > self._settings.max_history_messages:
            logger.warning(
                "History too long",
                extra={"count": history_count, "max": self._settings.max_history_messages},
            )
            raise RequestValidationException(
                f"El historial de mensajes es demasiado largo. "
                f"Máximo permitido: {self._settings.max_history_messages} mensajes.",
                status_code=400,
            )

        logger.debug(
            "Request validation completed successfully",
            extra={"question_length": question_length, "history_count": history_count},
        )
