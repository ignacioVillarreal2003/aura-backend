import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_action_service.document_action_state import DocumentActionState
from app.application.services.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.document_action_service.processors.reduce_document_action_processor.reduce_document_action_prompt import (
    REDUCE_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_GUIDANCE_PROMPT,
    DEFAULT_GUIDANCE_PROMPT,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class ReduceDocumentActionProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, state: DocumentActionState) -> None:
        if not state.partial_results:
            return

        partial_results = state.partial_results

        if len(partial_results) == 1:
            logger.debug("Single partial result — skipping LLM reduction step")
            state.result = partial_results[0]
            return

        logger.debug("Reducing partial results", extra={"partial_result_count": len(partial_results)})

        action_guidance = (
            REDUCE_GUIDANCE_PROMPT.get(state.action, DEFAULT_GUIDANCE_PROMPT)
            if state.action
            else DEFAULT_GUIDANCE_PROMPT
        )
        results_joined = "\n\n---\n\n".join(
            f"Sección {idx + 1}:\n{result}"
            for idx, result in enumerate(partial_results)
        )
        llm_input = [
            SystemMessage(content=REDUCE_SYSTEM_PROMPT),
            HumanMessage(
                content=REDUCE_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    results_joined=results_joined,
                )
            ),
        ]

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
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
