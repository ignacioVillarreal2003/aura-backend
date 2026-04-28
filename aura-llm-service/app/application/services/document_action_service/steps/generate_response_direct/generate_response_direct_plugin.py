import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document_action_service.steps.generate_response_direct.generate_response_direct_prompt import (
    ACTION_GUIDANCE,
    DEFAULT_ACTION_GUIDANCE,
    DIRECT_RESPONSE_HUMAN_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class GenerateResponseDirectPlugin(DocumentActionPlugin):
    @property
    def plugin_name(self) -> str:
        return "generate_response_direct"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return state.strategy == ProcessingStrategy.direct and bool(state.all_fragments)

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        logger.debug(
            "Executing direct response generation",
            extra={"fragment_count": len(state.all_fragments), "action": state.action},
        )

        action_guidance = (
            ACTION_GUIDANCE.get(state.action, DEFAULT_ACTION_GUIDANCE)
            if state.action
            else DEFAULT_ACTION_GUIDANCE
        )

        fragments_joined = self._build_fragments_text(state)

        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=DIRECT_RESPONSE_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    fragments_joined=fragments_joined,
                )
            ),
        ]

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            raw = await resources.llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Direct response generation LLM call failed")
            raise DocumentActionServiceException(
                "Error generating the document action response"
            ) from e

        result = raw.strip() if raw else ""
        if not result:
            logger.warning("LLM returned empty result in direct mode")
            raise DocumentActionServiceException("The model did not generate a valid response")

        state.result = result
        logger.debug("Direct response generation completed successfully")

    @staticmethod
    def _build_fragments_text(state: DocumentActionPipelineState) -> str:
        sections: list[str] = []
        for doc_id in state.document_ids:
            doc_fragments = state.fragments_by_document.get(doc_id, [])
            if not doc_fragments:
                continue
            fragment_texts = "\n\n".join(
                f"Fragmento {idx + 1}:\n{fragment.content}"
                for idx, fragment in enumerate(doc_fragments)
            )
            sections.append(f"--- Documento ID {doc_id} ---\n\n{fragment_texts}")
        return "\n\n===\n\n".join(sections)
