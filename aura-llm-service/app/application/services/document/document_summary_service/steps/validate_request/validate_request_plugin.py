import logging
from typing import Optional

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document.document_summary_service.steps.validate_request.validate_request_settings import (
    ValidateDocumentRequestSettings,
)

logger = logging.getLogger(__name__)


class ValidateRequestPlugin(DocumentSummaryPlugin):
    def __init__(
            self,
            validate_request_settings: Optional[ValidateDocumentRequestSettings] = None,
    ) -> None:
        self._settings = validate_request_settings or ValidateDocumentRequestSettings()

    @property
    def plugin_name(self) -> str:
        return "validate_request"

    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        logger.debug("Starting request validation")

        document_id = state.document_id
        if not (self._settings.min_document_id <= document_id <= self._settings.max_document_id):
            logger.warning(
                "Document ID validation failed: value out of allowed range",
                extra={
                    "document_id": document_id,
                    "min": self._settings.min_document_id,
                    "max": self._settings.max_document_id,
                },
            )
            raise RequestValidationException(
                f"El identificador del documento es inválido. "
                f"Debe estar entre {self._settings.min_document_id} y {self._settings.max_document_id}. "
                f"Valor recibido: {document_id}.",
                status_code=400,
            )

        logger.debug(
            "Request validation completed successfully",
            extra={"document_id": document_id},
        )
