import asyncio
import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_prompts import (
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
)
from app.application.services.generation_shared.processors.section_context_processor.section_context_settings import (
    SectionContextSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentSectionGroup
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class SectionContextProcessor:
    """Handles the secondary (section) context of the "section" expansion mode.

    Primaries are always kept verbatim by the renderer. This processor only acts
    on the secondary fragments: it leaves them verbatim when small, and condenses
    them with the LLM (query-aware, per group) when they exceed a conservative
    threshold, so the prompt can never explode with section context. No-op unless
    the state carries section groups.
    """

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            section_context_settings: Optional[SectionContextSettings] = None,
    ) -> None:
        self._settings = section_context_settings or SectionContextSettings()
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    @staticmethod
    def _secondary_chars(groups: list[FragmentSectionGroup]) -> int:
        return sum(
            len(fragment.effective_content or "")
            for group in groups
            for fragment in group.section_fragments
        )

    def is_needed(self, state: GenerationState) -> bool:
        groups = state.section_groups
        if not groups:
            return False
        return self._secondary_chars(groups) > self._settings.summarize_threshold_chars

    async def run(
            self,
            state: GenerationState,
            map_system_prompt: Optional[str] = None,
            map_human_prompt: Optional[str] = None,
    ) -> None:
        groups = state.section_groups
        if not groups:
            return
        if not self.is_needed(state):
            state.section_summary = None
            return

        system_prompt = map_system_prompt or MAP_SYSTEM_PROMPT
        human_prompt = map_human_prompt or MAP_HUMAN_PROMPT
        query = state.current_message.content

        try:
            llm = await self._build_llm()
            notes = await self._summarize_groups(llm, groups, query, system_prompt, human_prompt)
        except Exception:
            logger.warning(
                "Section context summarization failed; falling back to verbatim secondary context.",
                exc_info=True,
            )
            state.reduction_degraded = True
            state.section_summary = None
            return

        summary = self._assemble(notes)
        if not summary:
            state.section_summary = None
            return

        state.section_summary = summary[: self._settings.max_section_context_chars]
        logger.info(
            "Section context condensed.",
            extra={
                "groups": len(groups),
                "summarized_groups": len(notes),
                "output_chars": len(state.section_summary),
            },
        )

    async def _summarize_groups(
            self,
            llm: Runnable,
            groups: list[FragmentSectionGroup],
            query: str,
            system_prompt: str,
            human_prompt: str,
    ) -> list[str]:
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_groups)

        async def _one(group: FragmentSectionGroup) -> Optional[str]:
            if not group.section_fragments:
                return None
            label = self._group_label(group)
            fragments_text = "\n\n".join(
                (fragment.effective_content or "").strip()
                for fragment in group.section_fragments
                if (fragment.effective_content or "").strip()
            )
            if not fragments_text:
                return None
            async with semaphore:
                note = await self._extract(llm, system_prompt, human_prompt, fragments_text, query)
            if not note:
                return None
            return f"{label}\n{note}"

        results = await asyncio.gather(*(_one(group) for group in groups))
        return [note for note in results if note]

    @staticmethod
    def _group_label(group: FragmentSectionGroup) -> str:
        primary = group.primary
        document_name = primary.document.name if primary.document else ""
        section = primary.heading or primary.section_path or ""
        parts = [p for p in (document_name, section) if p]
        return f"[Sección: {' · '.join(parts)}]" if parts else "[Sección]"

    def _assemble(self, notes: list[str]) -> str:
        budget = self._settings.max_section_context_chars
        selected: list[str] = []
        used = 0
        for note in notes:
            addition = len(note) + (2 if selected else 0)
            if selected and used + addition > budget:
                break
            selected.append(note)
            used += addition
        return "\n\n".join(selected)

    async def _extract(
            self,
            llm: Runnable,
            system_prompt: str,
            human_prompt: str,
            fragments: str,
            query: str,
    ) -> Optional[str]:
        try:
            llm_input = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt.format(query=query, fragments=fragments)),
            ]
            return (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
        except Exception:
            logger.warning("A section group condensation failed; skipping it.", exc_info=True)
            return None

    async def _build_llm(self) -> Runnable:
        llm = await self._ollama_llm_facade.get_llm_base()
        if self._settings.temperature is not None:
            llm = llm.bind(temperature=self._settings.temperature)
        return llm
