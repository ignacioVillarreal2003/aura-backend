import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import contextmanager
from typing import Any, ClassVar, Iterator, Optional, Protocol

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import AppException, RequestValidationException
from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
from app.application.services.generation_shared.generation_observability import (
    generation_seconds,
    generation_total,
    log_extra,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.prompts.prompt_augmentation import augment_system_prompt
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_processor import (
    AttachedDocumentsProcessor,
)
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_processor import (
    ContextReductionProcessor,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_settings import (
    ContextReductionSettings,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_processor import (
    HistorySummarizationProcessor,
)
from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_settings import (
    HistorySummarizationSettings,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_processor import (
    QueryReformulationProcessor,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_settings import (
    QueryReformulationSettings,
)
from app.application.services.generation_shared.processors.section_context_processor.section_context_processor import (
    SectionContextProcessor,
)
from app.application.services.generation_shared.processors.section_context_processor.section_context_settings import (
    SectionContextSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

EMPTY_RESPONSE_MESSAGE = "El modelo de lenguaje devolvió una respuesta vacía."

INITIAL_PROGRESS_MESSAGE = "Procesando tu consulta..."

_LOADING_DOCUMENTS_MESSAGE = "Leyendo documentos adjuntos..."
_REFORMULATING_MESSAGE = "Interpretando y optimizando la consulta..."
_SEARCHING_COMPLEMENT_MESSAGE = "Buscando contexto adicional en la base de conocimiento..."
_SEARCHING_MESSAGE = "Buscando información relevante en los documentos..."
_REDUCING_MESSAGE = "Analizando el contenido de los documentos..."
_SUMMARIZING_HISTORY_MESSAGE = "Resumiendo la conversación previa..."


class GenerationRequest(Protocol):
    messages: Sequence[Message]
    chat_id: int
    document_ids: list[int]
    system_prompt: Optional[str]
    response_style: Optional[str]

class BaseGenerationService(ABC):
    label: ClassVar[str]
    exception_cls: ClassVar[type[AppException]]
    unexpected_error_message: ClassVar[str]
    generation_step_message: ClassVar[str] = ""

    default_retrieve_context: ClassVar[bool] = False
    default_process_documents: ClassVar[bool] = False
    summarize_history: ClassVar[bool] = False

    # Instrucción usada como input cuando el usuario adjunta documentos pero no
    # escribe ningún prompt. Vacía: el servicio exige siempre un mensaje del usuario.
    documents_only_instruction: ClassVar[str] = ""

    human_prompt: ClassVar[str]
    map_system_prompt: ClassVar[str]
    map_human_prompt: ClassVar[str]
    reduce_system_prompt: ClassVar[Optional[str]] = None
    reduce_human_prompt: ClassVar[Optional[str]] = None

    stream_progress_event: ClassVar[type]
    stream_complete_event: ClassVar[type]
    stream_error_event: ClassVar[type]

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: Optional[GenerationSettings] = None,
            *,
            query_reformulation_settings: Optional[QueryReformulationSettings] = None,
            context_retrieval_settings: Optional[ContextRetrievalSettings] = None,
            attached_documents_settings: Optional[AttachedDocumentsSettings] = None,
            context_reduction_settings: Optional[ContextReductionSettings] = None,
            history_summarization_settings: Optional[HistorySummarizationSettings] = None,
            section_context_settings: Optional[SectionContextSettings] = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            ollama_llm_facade, ollama_llm_invoker, query_reformulation_settings
        )
        self._context_processor = ContextRetrievalProcessor(
            document_context_provider, context_retrieval_settings
        )
        self._attached_processor = AttachedDocumentsProcessor(
            document_context_provider, attached_documents_settings
        )
        if context_reduction_settings is None:
            context_reduction_settings = ContextReductionSettings(
                max_context_chars=self._generation_settings.max_context_chars
            )
        self._reduction_processor = ContextReductionProcessor(
            ollama_llm_facade, ollama_llm_invoker, context_reduction_settings
        )
        self._history_summarization_processor = HistorySummarizationProcessor(
            ollama_llm_facade, ollama_llm_invoker, history_summarization_settings
        )
        self._section_processor = SectionContextProcessor(
            ollama_llm_facade, ollama_llm_invoker, section_context_settings
        )
        self._known_exceptions: tuple[type[Exception], ...] = (
            RequestValidationException,
            self.exception_cls,
            UnauthorizedException,
        )
        self._logger = logging.getLogger(type(self).__module__)
        self._logger.info("%s initialized", type(self).__name__)

    @abstractmethod
    def _system_prompt(self, request: Any) -> str:
        pass

    def _generation_progress_message(self, request: Any) -> str:
        return self.generation_step_message

    def _request_log_extra(self, request: Any) -> dict[str, Any]:
        return {
            "mode": getattr(request, "mode", None),
            "document_count": len(getattr(request, "document_ids", []) or []),
        }

    @staticmethod
    def _resolve_flag(request: Any, name: str, default: bool) -> bool:
        value = getattr(request, name, None)
        return default if value is None else bool(value)

    def _request_messages(self, request: Any) -> list[Message]:
        messages = list(getattr(request, "messages", None) or [])
        if messages:
            return messages
        if self.documents_only_instruction:
            return [Message(role=MessageRole.human, content=self.documents_only_instruction)]
        return messages

    def _build_state(self, request: Any, authenticated_user: AuthenticatedUser) -> GenerationState:
        retrieve_context = self._resolve_flag(request, "retrieve_context", self.default_retrieve_context)
        process_documents = self._resolve_flag(request, "process_documents", self.default_process_documents)
        return GenerationState.create(
            messages=self._request_messages(request),
            chat_id=request.chat_id,
            authenticated_user=authenticated_user,
            document_ids=list(getattr(request, "document_ids", []) or []),
            retrieve_context=retrieve_context,
            process_documents=process_documents,
        )

    async def _retrieve_rag_context(self, state: GenerationState) -> None:
        await self._reformulation_processor.run(state)
        await self._context_processor.run(state)

    async def _reduce_context(self, state: GenerationState) -> None:
        if state.section_groups:
            await self._section_processor.run(
                state,
                map_system_prompt=self.map_system_prompt,
                map_human_prompt=self.map_human_prompt,
            )
            return
        await self._reduction_processor.run(
            state,
            map_system_prompt=self.map_system_prompt,
            map_human_prompt=self.map_human_prompt,
            reduce_system_prompt=self.reduce_system_prompt,
            reduce_human_prompt=self.reduce_human_prompt,
        )

    _DEGRADATION_FLAGS: ClassVar[tuple[str, ...]] = (
        "reformulation_degraded",
        "retrieval_degraded",
        "reduction_degraded",
        "attached_degraded",
    )

    def _degraded_stages(self, state: GenerationState) -> list[str]:
        return [
            flag[: -len("_degraded")]
            for flag in self._DEGRADATION_FLAGS
            if getattr(state, flag)
        ]

    def _log_degradations(self, state: GenerationState) -> None:
        degraded = self._degraded_stages(state)
        if degraded:
            self._logger.warning(
                "%s context pipeline degraded; answer may be incomplete.",
                self.label,
                extra=log_extra(degraded_stages=degraded),
            )

    async def _summarize_history(self, state: GenerationState) -> None:
        await self._history_summarization_processor.run(
            state, self._generation_settings.history_messages_window
        )

    async def _collect_context(self, state: GenerationState) -> None:
        if self.summarize_history:
            await self._summarize_history(state)
        if state.process_documents:
            await self._attached_processor.run(state)
        if state.retrieve_context:
            await self._retrieve_rag_context(state)
        if state.process_documents or state.retrieve_context:
            await self._reduce_context(state)
        self._log_degradations(state)

    async def _collect_context_with_progress(self, state: GenerationState) -> AsyncIterator[Any]:
        if self.summarize_history and self._history_summarization_processor.is_needed(
            state, self._generation_settings.history_messages_window
        ):
            yield self.stream_progress_event(step="summarizing_history", message=_SUMMARIZING_HISTORY_MESSAGE)
            await self._summarize_history(state)
        gathered = False
        if state.process_documents:
            yield self.stream_progress_event(step="loading_documents", message=_LOADING_DOCUMENTS_MESSAGE)
            await self._attached_processor.run(state)
            gathered = True
        if state.retrieve_context:
            yield self.stream_progress_event(step="reformulating", message=_REFORMULATING_MESSAGE)
            await self._reformulation_processor.run(state)
            message = _SEARCHING_COMPLEMENT_MESSAGE if state.process_documents else _SEARCHING_MESSAGE
            yield self.stream_progress_event(step="searching", message=message)
            await self._context_processor.run(state)
            gathered = True
        if gathered:
            needs_reduction = (
                self._section_processor.is_needed(state)
                if state.section_groups
                else self._reduction_processor.is_needed(state)
            )
            if needs_reduction:
                yield self.stream_progress_event(step="reducing", message=_REDUCING_MESSAGE)
            await self._reduce_context(state)
        self._log_degradations(state)

    def _build_llm_messages(self, state: GenerationState, request: Any) -> list:
        context_block = build_context_block(
            state,
            self._generation_settings.effective_max_context_chars(),
            self._generation_settings.attached_reserve_ratio,
        )
        return build_generation_messages(
            augment_system_prompt(self._system_prompt(request), request.system_prompt, request.response_style),
            self.human_prompt,
            state,
            self._generation_settings.history_messages_window,
            context_block,
            self._generation_settings.max_history_chars,
        )

    @contextmanager
    def _observe(self, mode: str, authenticated_user: AuthenticatedUser, request: Any) -> Iterator[dict]:
        holder = {"outcome": "error"}
        start = time.perf_counter()
        user_id = getattr(authenticated_user, "id", None)
        initiated_extra = {"user_id": user_id, "call_mode": mode, **self._request_log_extra(request)}
        self._logger.info(
            "%s generation initiated",
            self.label.capitalize(),
            extra=log_extra(**initiated_extra),
        )
        try:
            yield holder
        finally:
            try:
                generation_seconds.labels(label=self.label, call_mode=mode).observe(time.perf_counter() - start)
                generation_total.labels(label=self.label, call_mode=mode, outcome=holder["outcome"]).inc()
            except Exception:
                self._logger.debug("Failed to record generation metrics.", exc_info=True)
            self._logger.info(
                "%s generation finished",
                self.label.capitalize(),
                extra=log_extra(user_id=user_id, call_mode=mode, outcome=holder["outcome"]),
            )
