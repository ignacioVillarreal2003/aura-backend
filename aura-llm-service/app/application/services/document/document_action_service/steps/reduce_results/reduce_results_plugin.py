import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)
from app.application.services.document.document_action_service.steps.reduce_results.reduce_results_prompt import (
    ACTION_REDUCE_GUIDANCE,
    DEFAULT_REDUCE_GUIDANCE,
    REDUCTION_HUMAN_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class ReduceResultsPlugin(DocumentActionPlugin):
    @property
    def plugin_name(self) -> str:
        return "reduce_results"

    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        return len(state.partial_results) > 0

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        partial_results = state.partial_results

        if len(partial_results) == 1:
            logger.debug("Single partial result — skipping LLM reduction step")
            state.result = partial_results[0]
            return

        logger.debug(
            "Reducing partial results",
            extra={"partial_result_count": len(partial_results)},
        )

        action_guidance = (
            ACTION_REDUCE_GUIDANCE.get(state.action, DEFAULT_REDUCE_GUIDANCE)
            if state.action
            else DEFAULT_REDUCE_GUIDANCE
        )

        results_joined = "\n\n---\n\n".join(
            f"Sección {idx + 1}:\n{result}"
            for idx, result in enumerate(partial_results)
        )

        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=REDUCTION_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    results_joined=results_joined,
                )
            ),
        ]

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            raw = await resources.llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Reduction LLM call failed")
            raise DocumentActionServiceException(
                "Error combining partial results into the final response"
            ) from e

        result = raw.strip() if raw else ""
        if not result:
            logger.warning("LLM returned empty result during reduction")
            raise DocumentActionServiceException("The model did not generate a valid final response")

        state.result = result
        logger.debug("Reduction completed successfully")
