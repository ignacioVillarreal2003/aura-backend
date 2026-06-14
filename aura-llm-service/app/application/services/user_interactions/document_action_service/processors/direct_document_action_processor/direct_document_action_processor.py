import logging
from collections.abc import AsyncIterator
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.user_interactions.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.application.services.user_interactions.document_action_service.document_action_state import DocumentActionState
from app.application.services.user_interactions.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.user_interactions.document_action_service.processors.direct_document_action_processor.direct_document_action_prompt import (
    DIRECT_SYSTEM_PROMPT,
    DIRECT_HUMAN_PROMPT,
    DIRECT_GUIDANCE_PROMPT,
    DEFAULT_GUIDANCE_PROMPT,
)
from app.application.services.generation_shared.prompts.prompt_augmentation import augment_system_prompt
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import DocumentActionStreamDelta
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)


class DirectDocumentActionProcessor:
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
            DIRECT_GUIDANCE_PROMPT.get(state.action, DEFAULT_GUIDANCE_PROMPT)
            if state.action
            else DEFAULT_GUIDANCE_PROMPT
        )
        system_content = augment_system_prompt(
            DIRECT_SYSTEM_PROMPT,
            state.system_prompt,
            state.response_style,
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(
                content=DIRECT_HUMAN_PROMPT.format(
                    action_guidance=action_guidance,
                    instruction=state.instruction,
                    fragments_joined=self._build_fragments_text(state),
                )
            ),
        ]

    async def run(self, state: DocumentActionState) -> None:
        if state.strategy != ProcessingStrategy.direct or not state.all_fragments:
            return

        logger.debug(
            "Executing direct response generation",
            extra={"fragment_count": len(state.all_fragments), "action": state.action},
        )

        llm_input = self._build_llm_input(state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Direct response generation LLM call failed")
            raise DocumentActionServiceException("Error generating the document action response") from e

        result = raw.strip() if raw else ""
        if not result:
            logger.warning("LLM returned empty result in direct mode")
            raise DocumentActionServiceException("The model did not generate a valid response")

        state.result = result
        logger.debug("Direct response generation completed successfully")

    async def stream(self, state: DocumentActionState) -> AsyncIterator[DocumentActionStreamDelta]:
        if state.strategy != ProcessingStrategy.direct or not state.all_fragments:
            return

        logger.debug(
            "Executing direct response generation (stream)",
            extra={"fragment_count": len(state.all_fragments), "action": state.action},
        )

        llm_input = self._build_llm_input(state)

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
                state.result += delta
                yield DocumentActionStreamDelta(text=delta)
        except Exception as e:
            logger.exception("Direct response generation streaming failed")
            raise DocumentActionServiceException("Error generating the document action response") from e

        if not state.result.strip():
            logger.warning("LLM stream produced no visible text in direct mode; falling back to non-stream")
            try:
                llm = await self._ollama_llm_facade.get_llm_base()
                raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            except Exception as e:
                logger.exception("Direct response generation non-stream fallback failed")
                raise DocumentActionServiceException("Error generating the document action response") from e
            if raw and raw.strip():
                state.result = raw.strip()
                yield DocumentActionStreamDelta(text=state.result)

        logger.debug("Direct response generation (stream) completed")

    @staticmethod
    def _build_fragments_text(state: DocumentActionState) -> str:
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
