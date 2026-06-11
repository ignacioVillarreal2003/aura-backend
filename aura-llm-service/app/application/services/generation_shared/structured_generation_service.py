"""Template base for the structured-generation services.

Checklist, quiz, timeline, lessons-learned, decision-brief and report all run
the same pipeline: load attached documents, optionally retrieve RAG context,
reduce the context if it overflows, invoke the LLM and parse its output into a
typed response. Subclasses only supply prompts, output parsing and response
building; the pipeline, streaming progress events and the error contract live
here so they stay consistent across services.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any, ClassVar, Generic, Optional, Protocol, TypeVar

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import AppException, RequestValidationException
from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor import (
    AttachedDocumentsProcessor,
)
from app.application.services.generation_shared.processors.context_reduction_processor import (
    ContextReductionProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.query_reformulation_processor import (
    QueryReformulationProcessor,
)
from app.application.services.generation_shared.prompt_augmentation import augment_system_prompt
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

_RAG_MODE_VALUE = "rag"

_EMPTY_RESPONSE_MESSAGE = "El modelo de lenguaje devolvió una respuesta vacía."

_LOADING_DOCUMENTS_MESSAGE = "Leyendo documentos adjuntos..."
_SEARCHING_COMPLEMENT_MESSAGE = "Buscando contexto adicional en la base de conocimiento..."
_SEARCHING_MESSAGE = "Buscando información relevante en los documentos..."


class StructuredGenerationRequest(Protocol):
    messages: Sequence[Message]
    chat_id: int
    mode: Any
    document_ids: list[int]
    system_prompt: Optional[str]
    response_style: Optional[str]


TRequest = TypeVar("TRequest", bound=StructuredGenerationRequest)
TParsed = TypeVar("TParsed")
TResponse = TypeVar("TResponse")


class StructuredGenerationService(ABC, Generic[TRequest, TParsed, TResponse]):
    # Human-readable name used in log messages, e.g. "checklist".
    label: ClassVar[str]
    # Service-specific exception type; must accept (message, *, status_code).
    exception_cls: ClassVar[type[AppException]]
    # User-facing Spanish message for unexpected (500) failures.
    unexpected_error_message: ClassVar[str]
    # Progress message emitted right before the LLM call (see also
    # _generation_progress_message for per-request variants).
    generation_step_message: ClassVar[str] = ""

    # Stream event models (uniform shapes across services):
    # progress(step, message) / complete(result) / error(message, code).
    stream_progress_event: ClassVar[type]
    stream_complete_event: ClassVar[type]
    stream_error_event: ClassVar[type]

    # Prompts.
    human_prompt: ClassVar[str]
    extraction_system_prompt: ClassVar[str]
    extraction_human_prompt: ClassVar[str]
    # Default RAG query expansions (see also _rag_queries for per-request variants).
    rag_queries: ClassVar[list[str]] = []

    # Whether the LLM is invoked in JSON mode or free-form text mode.
    uses_json_mode: ClassVar[bool] = True

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._known_exceptions: tuple[type[Exception], ...] = (
            RequestValidationException,
            self.exception_cls,
            UnauthorizedException,
        )
        # Log under the subclass module so records keep their service of origin.
        self._logger = logging.getLogger(type(self).__module__)
        self._logger.info("%s initialized", type(self).__name__)

    # ------------------------------------------------------------------ hooks

    @abstractmethod
    def _system_prompt(self, request: TRequest) -> str:
        """Base system prompt before operator augmentation."""

    @abstractmethod
    def _parse_output(self, raw: str, request: TRequest) -> TParsed:
        """Parse the raw LLM output; raise exception_cls(status_code=502) if unusable."""

    @abstractmethod
    def _build_response(
            self,
            state: GenerationState,
            request: TRequest,
            parsed: TParsed,
            raw: str,
    ) -> TResponse:
        """Build the typed response from the parsed output."""

    def _rag_queries(self, request: TRequest) -> list[str]:
        return self.rag_queries

    def _postprocess_raw(self, raw: str) -> str:
        return raw

    def _generation_progress_message(self, request: TRequest) -> str:
        return self.generation_step_message

    def _request_log_extra(self, request: TRequest) -> dict[str, Any]:
        return {"mode": request.mode}

    def _result_log_extra(self, parsed: TParsed) -> dict[str, Any]:
        return {}

    # --------------------------------------------------------------- pipeline

    def _build_state(
            self,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=list(request.messages),
            chat_id=request.chat_id,
            is_rag=request.mode == _RAG_MODE_VALUE,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _retrieve_rag_context(self, state: GenerationState, request: TRequest) -> None:
        await self._reformulation_processor.run(state)
        await self._context_processor.run(state, self._rag_queries(request))

    async def _reduce_context(self, state: GenerationState) -> None:
        await self._reduction_processor.run(
            state, self.extraction_system_prompt, self.extraction_human_prompt
        )

    async def _collect_context(self, state: GenerationState, request: TRequest) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._retrieve_rag_context(state, request)
        await self._reduce_context(state)

    async def _collect_context_with_progress(
            self,
            state: GenerationState,
            request: TRequest,
    ) -> AsyncIterator[Any]:
        """Same pipeline as _collect_context, interleaving stream progress events."""
        if state.document_ids:
            yield self.stream_progress_event(step="loading_documents", message=_LOADING_DOCUMENTS_MESSAGE)
            await self._attached_processor.run(state)
            if state.is_rag:
                yield self.stream_progress_event(step="searching", message=_SEARCHING_COMPLEMENT_MESSAGE)
                await self._retrieve_rag_context(state, request)
        elif state.is_rag:
            yield self.stream_progress_event(step="searching", message=_SEARCHING_MESSAGE)
            await self._retrieve_rag_context(state, request)
        await self._reduce_context(state)

    async def _invoke(self, state: GenerationState, request: TRequest) -> str:
        context_block = build_context_block(
            state,
            self._generation_settings.max_context_chars,
            self._generation_settings.attached_reserve_ratio,
        )
        llm_messages = build_generation_messages(
            augment_system_prompt(self._system_prompt(request), request.system_prompt, request.response_style),
            self.human_prompt,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await (
            self._ollama_llm_facade.get_llm_json()
            if self.uses_json_mode
            else self._ollama_llm_facade.get_llm_base()
        )
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise self.exception_cls(_EMPTY_RESPONSE_MESSAGE, status_code=502)
        return self._postprocess_raw(raw)

    @staticmethod
    def _conversation_with_answer(state: GenerationState, answer: str) -> list[Message]:
        return [*state.messages, Message(role=MessageRole.assistant, content=answer)]

    # ------------------------------------------------------------- public API

    async def generate(
            self,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TResponse:
        self._logger.info(
            "%s generation initiated",
            self.label.capitalize(),
            extra={"user_id": authenticated_user.id, **self._request_log_extra(request)},
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._collect_context(state, request)

            raw = await self._invoke(state, request)
            parsed = self._parse_output(raw, request)

            self._logger.info(
                "%s generation completed",
                self.label.capitalize(),
                extra={
                    "user_id": authenticated_user.id,
                    "fragments_used": len(state.all_fragments),
                    **self._result_log_extra(parsed),
                },
            )
            return self._build_response(state, request, parsed, raw)

        except self._known_exceptions:
            raise
        except Exception as e:
            self._logger.exception(
                "Unexpected error during %s generation",
                self.label,
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise self.exception_cls(self.unexpected_error_message, status_code=500) from e

    async def generate_stream(
            self,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[Any]:
        try:
            state = self._build_state(request, authenticated_user)
            async for progress_event in self._collect_context_with_progress(state, request):
                yield progress_event

            yield self.stream_progress_event(
                step="generation",
                message=self._generation_progress_message(request),
            )

            raw = await self._invoke(state, request)
            parsed = self._parse_output(raw, request)

            yield self.stream_complete_event(result=self._build_response(state, request, parsed, raw))

        except self._known_exceptions as e:
            self._logger.warning(
                "Known error during %s stream generation",
                self.label,
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield self.stream_error_event(message=str(e), code=type(e).__name__)
        except Exception as e:
            self._logger.exception(
                "Unexpected error during %s stream generation",
                self.label,
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield self.stream_error_event(message=self.unexpected_error_message, code="internal_error")
