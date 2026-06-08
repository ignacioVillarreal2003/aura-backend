import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class ContextReductionProcessor:
    def __init__(
            self,
            settings: GenerationSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._settings = settings
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    def is_needed(self, state: GenerationState) -> bool:
        if not self._settings.enable_context_reduction:
            return False
        fragments = state.all_fragments
        if not fragments:
            return False
        total = sum(len(f.content) for f in fragments)
        return total > self._settings.max_context_chars

    async def run(
            self,
            state: GenerationState,
            extraction_system_prompt: str,
            extraction_human_prompt: str,
    ) -> None:
        if not self.is_needed(state):
            return

        units = self._fragment_units(state.all_fragments)
        consigna = state.current_message.content
        synthesis = await self._reduce(units, consigna, extraction_system_prompt, extraction_human_prompt)
        state.reduced_context = synthesis or None
        logger.debug(
            "Context reduction completed",
            extra={
                "source_fragments": len(state.all_fragments),
                "synthesis_chars": len(synthesis or ""),
            },
        )

    def _fragment_units(self, fragments: list[FragmentResponse]) -> list[str]:
        budget = self._settings.reduction_batch_chars
        units: list[str] = []
        for frag in fragments:
            content = frag.content
            label = frag.document.name
            if len(content) <= budget:
                units.append(f"[{label}] {content}")
            else:
                for i in range(0, len(content), budget):
                    units.append(f"[{label}] {content[i:i + budget]}")
        return units

    def _batches(self, units: list[str]) -> list[list[str]]:
        budget = self._settings.reduction_batch_chars
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

    async def _reduce(
            self,
            units: list[str],
            consigna: str,
            system_prompt: str,
            human_prompt: str,
    ) -> str:
        current = units
        passes = 0
        while True:
            batches = self._batches(current)
            extracted: list[str] = []
            for batch in batches:
                note = await self._extract("\n\n".join(batch), consigna, system_prompt, human_prompt)
                if note:
                    extracted.append(note)

            passes += 1
            combined = "\n\n".join(extracted)

            fits = len(combined) <= self._settings.max_context_chars
            exhausted = passes >= self._settings.max_reduction_passes
            converged = len(batches) <= 1
            if fits or exhausted or converged:
                return combined[:self._settings.max_context_chars]

            current = extracted

    async def _extract(
            self,
            text: str,
            consigna: str,
            system_prompt: str,
            human_prompt: str,
    ) -> str:
        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            llm_input = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt.format(input=consigna, fragments=text)),
            ]
            return (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
        except Exception:
            logger.warning("Extraction pass failed; skipping batch", exc_info=True)
            return ""
