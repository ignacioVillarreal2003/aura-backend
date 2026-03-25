import logging

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)

logger = logging.getLogger(__name__)


class ValidateRequestPlugin(DocumentQuestionPlugin):
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
                "La pregunta no puede estar vacía. Por favor, proporcione una pregunta válida.",
                status_code=400,
            )

        question_length = len(question.strip())
        if question_length < resources.settings.min_question_length:
            raise RequestValidationException(
                f"La pregunta es demasiado corta. Debe tener al menos "
                f"{resources.settings.min_question_length} caracteres.",
                status_code=400,
            )

        if question_length > resources.settings.max_question_length:
            raise RequestValidationException(
                f"La pregunta es demasiado larga. No debe exceder "
                f"{resources.settings.max_question_length} caracteres.",
                status_code=400,
            )

        if len(state.history_messages) > resources.settings.max_history_messages:
            raise RequestValidationException(
                f"El historial de mensajes es demasiado largo. Máximo permitido: "
                f"{resources.settings.max_history_messages} mensajes.",
                status_code=400,
            )

        logger.debug("Request validation completed successfully")
