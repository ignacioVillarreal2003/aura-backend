import logging

from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document_action_service.steps.fallback_response.fallback_response_prompt import (
    FALLBACK_RESPONSE_MESSAGE,
)

logger = logging.getLogger(__name__)


class FallbackResponsePlugin(DocumentActionPlugin):
    @property
    def plugin_name(self) -> str:
        return "fallback_response"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return not state.result

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        logger.warning(
            "No result was generated — applying fallback",
            extra={
                "document_ids": state.document_ids,
                "fragment_count": len(state.all_fragments),
            },
        )
        state.result = FALLBACK_RESPONSE_MESSAGE
