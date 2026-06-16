from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Generic, Optional, TypeVar

from app.application.services.generation_shared.base_generation_service import (
    EMPTY_RESPONSE_MESSAGE,
    BaseGenerationService,
    GenerationRequest,
)
from app.application.services.generation_shared.generation_observability import log_extra
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.configuration.tracing import trace_generation
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

TRequest = TypeVar("TRequest", bound=GenerationRequest)
TResponse = TypeVar("TResponse")


class StreamingGenerationService(BaseGenerationService, Generic[TRequest, TResponse]):
    stream_delta_event: ClassVar[type]

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: Optional[GenerationSettings] = None,
            **processor_settings: Any,
    ) -> None:
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            generation_settings=generation_settings,
            **processor_settings,
        )
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker

    @abstractmethod
    def _build_response(self, state: GenerationState, request: TRequest, answer: str) -> TResponse:
        pass

    def _postprocess_answer(self, answer: str) -> str:
        return answer

    async def _stream_pre_generation_events(
            self,
            state: GenerationState,
            request: TRequest,
    ) -> AsyncIterator[Any]:
        for _ in ():
            yield _

    async def _invoke(self, state: GenerationState, request: TRequest) -> str:
        llm_messages = self._build_llm_messages(state, request)
        llm = await self._ollama_llm_facade.get_llm_base()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise self.exception_cls(EMPTY_RESPONSE_MESSAGE, status_code=502)
        return self._postprocess_answer(raw)

    @trace_generation()
    async def generate(
            self,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TResponse:
        with self._observe("sync", authenticated_user, request) as obs:
            try:
                state = self._build_state(request, authenticated_user)
                await self._collect_context(state)

                answer = await self._invoke(state, request)
                response = self._build_response(state, request, answer)

                obs["outcome"] = "success"
                self._logger.info(
                    "%s generation completed",
                    self.label.capitalize(),
                    extra=log_extra(user_id=authenticated_user.id, fragments_used=len(state.all_fragments)),
                )
                return response

            except self._known_exceptions:
                obs["outcome"] = "known_error"
                raise
            except Exception as e:
                self._logger.exception(
                    "Unexpected error during %s generation",
                    self.label,
                    extra=log_extra(user_id=authenticated_user.id, error_type=type(e).__name__),
                )
                raise self.exception_cls(self.unexpected_error_message, status_code=500) from e

    @trace_generation()
    async def generate_stream(
            self,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[Any]:
        with self._observe("stream", authenticated_user, request) as obs:
            try:
                state = self._build_state(request, authenticated_user)
                async for progress_event in self._collect_context_with_progress(state):
                    yield progress_event

                async for pre_event in self._stream_pre_generation_events(state, request):
                    yield pre_event

                yield self.stream_progress_event(
                    step="generation",
                    message=self._generation_progress_message(request),
                )

                answer = ""
                llm_messages = self._build_llm_messages(state, request)
                llm = await self._ollama_llm_facade.get_llm_base()
                async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_messages):
                    answer += delta
                    yield self.stream_delta_event(text=delta)

                answer = answer.strip()
                if not answer:
                    self._logger.warning(
                        "%s stream produced no text; falling back to non-stream invocation.",
                        self.label,
                        extra=log_extra(user_id=authenticated_user.id),
                    )
                    answer = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
                    if answer:
                        yield self.stream_delta_event(text=answer)

                if not answer:
                    raise self.exception_cls(EMPTY_RESPONSE_MESSAGE, status_code=502)

                answer = self._postprocess_answer(answer)
                yield self.stream_complete_event(result=self._build_response(state, request, answer))
                obs["outcome"] = "success"

            except self._known_exceptions as e:
                obs["outcome"] = "known_error"
                self._logger.warning(
                    "Known error during %s stream generation",
                    self.label,
                    extra=log_extra(user_id=authenticated_user.id, error_type=type(e).__name__),
                )
                yield self.stream_error_event(message=str(e), code=type(e).__name__)
            except LLMInvocationError as e:
                obs["outcome"] = "known_error"
                self._logger.exception("LLM error during %s streaming", self.label)
                yield self.stream_error_event(message=str(e), code=type(e).__name__)
            except Exception as e:
                self._logger.exception(
                    "Unexpected error during %s stream generation",
                    self.label,
                    extra=log_extra(user_id=authenticated_user.id, error_type=type(e).__name__),
                )
                yield self.stream_error_event(message=self.unexpected_error_message, code="internal_error")
