import logging
from collections.abc import AsyncIterator
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.user_interactions.document_action_service.document_action_state import DocumentActionState
from app.application.services.user_interactions.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.user_interactions.document_action_service.processors.reduce_document_action_processor.reduce_document_action_prompt import (
    REDUCE_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_GUIDANCE_PROMPT,
    DEFAULT_GUIDANCE_PROMPT,
)
from app.application.services.generation_shared.prompt_augmentation import augment_system_prompt
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import DocumentActionStreamDelta
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)


class ReduceDocumentActionProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker

    def _build_llm_input(self, state: DocumentActionState) -> list:
        action_guidance = (
            REDUCE_GUIDANCE_PROMPT.get(state.action, DEFAULT_GUIDANCE_PROMPT)
            if state.action
            else DEFAULT_GUIDANCE_PROMPT
        )
        results_joined = "\n\n---\n\n".join(
            f"Sección {idx + 1}:\n{result}"
            for idx, result in enumerate(state.partial_results)
        )
        system_content = augment_system_prompt(
            REDUCE_SYSTEM_PROMPT,
            state.system_prompt,
            state.response_style,
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(
                content=REDUCE_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    results_joined=results_joined,
                )
            ),
        ]

    async def run(self, state: DocumentActionState) -> None:
        if not state.partial_results:
            return

        if len(state.partial_results) == 1:
            logger.debug("Single partial result — skipping LLM reduction step")
            state.result = state.partial_results[0]
            return

        logger.debug("Reducing partial results", extra={"partial_result_count": len(state.partial_results)})

        llm_input = self._build_llm_input(state)

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

    async def stream(self, state: DocumentActionState) -> AsyncIterator[DocumentActionStreamDelta]:
        if not state.partial_results:
            return

        if len(state.partial_results) == 1:
            logger.debug("Single partial result — skipping LLM reduction step (stream)")
            state.result = state.partial_results[0]
            yield DocumentActionStreamDelta(text=state.partial_results[0])
            return

        logger.debug("Reducing partial results (stream)", extra={"partial_result_count": len(state.partial_results)})

        llm_input = self._build_llm_input(state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
                state.result += delta
                yield DocumentActionStreamDelta(text=delta)
        except Exception as e:
            logger.exception("Reduction streaming failed")
            raise DocumentActionServiceException(
                "Error combining partial results into the final response"
            ) from e

        if not state.result.strip():
            logger.warning("LLM stream produced no visible text during reduction; falling back to non-stream")
            try:
                llm = await self._ollama_llm_facade.get_llm_base()
                raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            except Exception as e:
                logger.exception("Reduction non-stream fallback failed")
                raise DocumentActionServiceException(
                    "Error combining partial results into the final response"
                ) from e
            if raw and raw.strip():
                state.result = raw.strip()
                yield DocumentActionStreamDelta(text=state.result)

        logger.debug("Reduction (stream) completed")
