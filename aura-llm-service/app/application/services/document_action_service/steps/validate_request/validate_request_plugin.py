import logging
from typing import Optional

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document_action_service.steps.validate_request.validate_request_settings import (
    ValidateActionRequestSettings,
)

logger = logging.getLogger(__name__)


class ValidateRequestPlugin(DocumentActionPlugin):
    def __init__(
            self,
            validate_request_settings: Optional[ValidateActionRequestSettings] = None,
    ) -> None:
        self._settings = validate_request_settings or ValidateActionRequestSettings()

    @property
    def plugin_name(self) -> str:
        return "validate_request"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        logger.debug("Starting request validation")

        if not state.document_ids:
            raise RequestValidationException(
                "Debe enviar al menos un identificador de documento.",
                status_code=400,
            )

        if len(state.document_ids) > self._settings.max_document_ids:
            raise RequestValidationException(
                f"Se excede el máximo de documentos permitidos. "
                f"Máximo: {self._settings.max_document_ids}. "
                f"Recibidos: {len(state.document_ids)}.",
                status_code=400,
            )

        for doc_id in state.document_ids:
            if not (self._settings.min_document_id <= doc_id <= self._settings.max_document_id):
                raise RequestValidationException(
                    f"El identificador del documento es inválido: {doc_id}. "
                    f"Debe estar entre {self._settings.min_document_id} y {self._settings.max_document_id}.",
                    status_code=400,
                )

        instruction = state.instruction.strip()
        if not instruction:
            raise RequestValidationException(
                "La instrucción no puede estar vacía.",
                status_code=400,
            )

        instruction_length = len(instruction)
        if instruction_length < self._settings.min_instruction_length:
            raise RequestValidationException(
                f"La instrucción es demasiado corta. "
                f"Debe tener al menos {self._settings.min_instruction_length} caracteres.",
                status_code=400,
            )

        if instruction_length > self._settings.max_instruction_length:
            raise RequestValidationException(
                f"La instrucción es demasiado larga. "
                f"No debe exceder {self._settings.max_instruction_length} caracteres.",
                status_code=400,
            )

        logger.debug(
            "Request validation completed successfully",
            extra={
                "document_count": len(state.document_ids),
                "instruction_length": instruction_length,
                "action": state.action.value if state.action else None,
            },
        )
