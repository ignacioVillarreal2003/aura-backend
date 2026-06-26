import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.token_estimation import tokens_to_chars
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_prompts import (
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_settings import (
    ContextReductionSettings,
)
from app.application.services.generation_shared.processors.processor_observability import (
    log_extra,
    reduction_batch_failures_total,
    reduction_compression_ratio,
    reduction_outcome_total,
    reduction_passes,
    timed,
)
from app.configuration.tracing import generation_span
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_STAGE = "context_reduction"
_NOTE_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class _ReductionResult:
    text: str
    outcome: str
    passes_used: int
    batches_total: int
    failed_batches: int
    input_chars: int
    output_chars: int
    degraded: bool


class ContextReductionProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            context_reduction_settings: Optional[ContextReductionSettings] = None,
    ) -> None:
        self._settings = context_reduction_settings or ContextReductionSettings()
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    def is_needed(self, state: GenerationState) -> bool:
        fragments = state.all_fragments
        if not fragments:
            return False
        total = sum(len(f.effective_content) for f in fragments)
        return total > self._settings.max_context_chars

    async def run(
            self,
            state: GenerationState,
            map_system_prompt: Optional[str] = None,
            map_human_prompt: Optional[str] = None,
            reduce_system_prompt: Optional[str] = None,
            reduce_human_prompt: Optional[str] = None,
    ) -> None:
        if not self.is_needed(state):
            return

        prompts = _ReductionPrompts(
            map_system=map_system_prompt or MAP_SYSTEM_PROMPT,
            map_human=map_human_prompt or MAP_HUMAN_PROMPT,
            reduce_system=reduce_system_prompt or REDUCE_SYSTEM_PROMPT,
            reduce_human=reduce_human_prompt or REDUCE_HUMAN_PROMPT,
        )

        with timed(_STAGE), generation_span(_STAGE, state.current_message.content):
            llm = await self._build_llm()
            fragment_units = self._fragment_units(state.all_fragments)
            query = state.current_message.content
            result = await self._reduce(llm, fragment_units, query, prompts)

        state.reduced_context = result.text or None
        if result.degraded:
            state.reduction_degraded = True

        self._record(state, result)

    def _record(self, state: GenerationState, result: _ReductionResult) -> None:
        reduction_passes.observe(result.passes_used)
        reduction_outcome_total.labels(outcome=result.outcome).inc()
        if result.failed_batches:
            reduction_batch_failures_total.inc(result.failed_batches)
        if result.input_chars > 0:
            reduction_compression_ratio.observe(result.output_chars / result.input_chars)

        if not result.text:
            logger.warning(
                "Context reduction produced no output; falling back to raw fragments (may exceed budget).",
                extra=log_extra(source_fragments=len(state.all_fragments), outcome=result.outcome),
            )
        elif result.degraded:
            logger.warning(
                "Context reduction did not fit the budget; notes were dropped to fit.",
                extra=log_extra(outcome=result.outcome, passes_used=result.passes_used,
                                output_chars=result.output_chars),
            )

        logger.info(
            "Context reduction completed.",
            extra=log_extra(
                source_fragments=len(state.all_fragments),
                input_chars=result.input_chars,
                output_chars=result.output_chars,
                compression_ratio=(round(result.output_chars / result.input_chars, 3)
                                   if result.input_chars else None),
                passes_used=result.passes_used,
                batches_total=result.batches_total,
                failed_batches=result.failed_batches,
                outcome=result.outcome,
            ),
        )

    async def _build_llm(self) -> Runnable:
        llm = await self._ollama_llm_facade.get_llm_base()
        if self._settings.temperature is not None:
            llm = llm.bind(temperature=self._settings.temperature)
        return llm

    def _batch_char_budget(self) -> int:
        token_budget_chars = tokens_to_chars(self._settings.max_batch_tokens)
        return min(self._settings.max_batch_chars, token_budget_chars)

    def _fragment_units(self, fragments: list[FragmentResponse]) -> list[str]:
        budget = self._batch_char_budget()
        units: list[str] = []
        for frag in fragments:
            label = f"[{frag.document.name}] "
            content = frag.effective_content
            chunk_budget = max(1, budget - len(label))
            if len(content) <= chunk_budget:
                units.append(f"{label}{content}")
            else:
                for i in range(0, len(content), chunk_budget):
                    units.append(f"{label}{content[i:i + chunk_budget]}")
        return units

    def _batches(self, units: list[str]) -> list[list[str]]:
        budget = self._batch_char_budget()
        sep_len = len(_NOTE_SEPARATOR)
        batches: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for unit in units:
            addition = len(unit) + (sep_len if current else 0)
            if current and current_len + addition > budget:
                batches.append(current)
                current, current_len = [unit], len(unit)
            else:
                current.append(unit)
                current_len += addition
        if current:
            batches.append(current)
        return batches

    async def _reduce(
            self,
            llm: Runnable,
            fragments: list[str],
            query: str,
            prompts: "_ReductionPrompts",
    ) -> _ReductionResult:
        start = time.monotonic()
        budget = self._settings.max_context_chars
        input_chars = sum(len(unit) for unit in fragments)

        current = fragments
        extracted: list[str] = []
        prev_len: Optional[int] = None
        passes = 0
        total_batches = 0
        total_failed = 0
        outcome = "empty"

        while True:
            if passes > 0 and (time.monotonic() - start) > self._settings.deadline_seconds:
                outcome = "timeout"
                break

            is_map = passes == 0
            system_prompt = prompts.map_system if is_map else prompts.reduce_system
            human_prompt = prompts.map_human if is_map else prompts.reduce_human

            batches = self._batches(current)
            with generation_span(f"{_STAGE}.pass_{passes}"):
                notes, failed = await self._run_pass(llm, batches, query, system_prompt, human_prompt)

            passes += 1
            total_batches += len(batches)
            total_failed += failed

            if not notes:
                outcome = "empty"
                extracted = []
                break

            extracted = notes
            combined_len = sum(len(note) for note in notes) + len(_NOTE_SEPARATOR) * (len(notes) - 1)

            if combined_len <= budget:
                outcome = "fit"
                break
            if len(batches) <= 1:
                outcome = "converged"
                break
            if prev_len is not None and combined_len >= prev_len:
                outcome = "not_shrinking"
                break
            if passes >= self._settings.max_passes:
                outcome = "exhausted"
                break

            prev_len = combined_len
            current = notes

        text = self._fit_notes(extracted) if extracted else ""
        final_len = sum(len(n) for n in extracted) + len(_NOTE_SEPARATOR) * (len(extracted) - 1) if extracted else 0
        degraded = (not extracted) or outcome == "timeout" or final_len > budget

        return _ReductionResult(
            text=text,
            outcome=outcome,
            passes_used=passes,
            batches_total=total_batches,
            failed_batches=total_failed,
            input_chars=input_chars,
            output_chars=len(text),
            degraded=degraded,
        )

    async def _run_pass(
            self,
            llm: Runnable,
            batches: list[list[str]],
            query: str,
            system_prompt: str,
            human_prompt: str,
    ) -> tuple[list[str], int]:
        semaphore = asyncio.Semaphore(self._settings.max_concurrent_batches)

        async def _guarded(batch: list[str]) -> Optional[str]:
            async with semaphore:
                return await self._extract(llm, system_prompt, human_prompt, _NOTE_SEPARATOR.join(batch), query)

        results = await asyncio.gather(*(_guarded(batch) for batch in batches))
        notes = [note for note in results if note]
        failed = sum(1 for note in results if note is None)
        return notes, failed

    def _fit_notes(self, notes: list[str]) -> str:
        budget = self._settings.max_context_chars
        selected: list[str] = []
        used = 0
        for note in notes:
            addition = len(note) + (len(_NOTE_SEPARATOR) if selected else 0)
            if selected and used + addition > budget:
                break
            selected.append(note)
            used += addition
        combined = _NOTE_SEPARATOR.join(selected)
        return combined[:budget]

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
            logger.warning("Extraction batch failed; skipping.", extra=log_extra(), exc_info=True)
            return None


class _ReductionPrompts:
    __slots__ = ("map_system", "map_human", "reduce_system", "reduce_human")

    def __init__(
            self,
            map_system: str,
            map_human: str,
            reduce_system: str,
            reduce_human: str,
    ) -> None:
        self.map_system = map_system
        self.map_human = map_human
        self.reduce_system = reduce_system
        self.reduce_human = reduce_human
