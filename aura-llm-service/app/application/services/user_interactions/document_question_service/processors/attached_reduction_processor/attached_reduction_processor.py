import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.user_interactions.document_question_service.document_question_state import (
    DocumentQuestionState,
)
from app.application.services.user_interactions.document_question_service.processors.attached_reduction_processor.attached_reduction_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class AttachedReductionProcessor:
    def __init__(
            self,
            settings: DocumentQuestionServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._settings = settings
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    def is_needed(self, state: DocumentQuestionState) -> bool:
        if not state.attached_fragments:
            return False
        total = sum(len(f.content) for f in state.attached_fragments)
        return total > self._settings.max_context_chars

    async def run(self, state: DocumentQuestionState) -> None:
        if not self.is_needed(state):
            return

        question = state.base_question or state.current_message.content
        units = self._build_units(state.attached_fragments)
        reduced = await self._reduce(units, question)

        state.reduced_attached_context = reduced or None
        logger.debug(
            "Attached fragments reduction completed",
            extra={
                "source_fragments": len(state.attached_fragments),
                "reduced_chars": len(reduced),
                "user_id": state.authenticated_user.id,
            },
        )

    def _build_units(self, fragments: list[FragmentResponse]) -> list[str]:
        budget = self._settings.attached_reduction_batch_chars
        units: list[str] = []
        for frag in fragments:
            label = frag.document.name
            content = frag.content
            if len(content) <= budget:
                units.append(f"[{label}] {content}")
            else:
                for i in range(0, len(content), budget):
                    units.append(f"[{label}] {content[i:i + budget]}")
        return units

    def _batches(self, units: list[str]) -> list[list[str]]:
        budget = self._settings.attached_reduction_batch_chars
        batches: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for unit in units:
            if current and current_len + len(unit) > budget:
                batches.append(current)
                current, current_len = [], 0
            current.append(unit)
            current_len += len(unit)
        if current:
            batches.append(current)
        return batches

    async def _reduce(self, units: list[str], question: str) -> str:
        current = units
        for _ in range(self._settings.attached_max_reduction_passes):
            batches = self._batches(current)
            extracted: list[str] = []
            for batch in batches:
                note = await self._extract("\n\n".join(batch), question)
                if note:
                    extracted.append(note)

            combined = "\n\n".join(extracted)
            fits = len(combined) <= self._settings.max_context_chars
            converged = len(batches) <= 1
            if fits or converged:
                return combined[:self._settings.max_context_chars]

            current = extracted if extracted else current
            if not extracted:
                break

        return "\n\n".join(current)[:self._settings.max_context_chars]

    async def _extract(self, text: str, question: str) -> str:
        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            llm_input = [
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(
                    content=EXTRACTION_HUMAN_PROMPT.format(
                        question=question,
                        fragments=text,
                    )
                ),
            ]
            return (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
        except Exception:
            logger.warning("Extraction pass failed for attached fragments; skipping batch", exc_info=True)
            return ""
