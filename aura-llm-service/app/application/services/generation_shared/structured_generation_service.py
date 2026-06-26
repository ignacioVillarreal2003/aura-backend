from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Generic, TypeVar

from app.application.services.generation_shared.base_generation_service import (
    EMPTY_RESPONSE_MESSAGE,
    INITIAL_PROGRESS_MESSAGE,
    BaseGenerationService,
    GenerationRequest,
)
from app.application.services.generation_shared.generation_observability import log_extra
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.configuration.tracing import trace_generation
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS

TRequest = TypeVar("TRequest", bound=GenerationRequest)
TParsed = TypeVar("TParsed")
TResponse = TypeVar("TResponse")


class StructuredGenerationService(BaseGenerationService, Generic[TRequest, TParsed, TResponse]):
    uses_json_mode: ClassVar[bool] = True

    @abstractmethod
    def _parse_output(self, raw: str, request: TRequest) -> TParsed:
        pass

    @abstractmethod
    def _build_response(
            self,
            state: GenerationState,
            request: TRequest,
            parsed: TParsed,
            raw: str,
    ) -> TResponse:
        pass

    def _postprocess_raw(self, raw: str) -> str:
        return raw

    def _result_log_extra(self, parsed: TParsed) -> dict[str, Any]:
        return {}

    async def _invoke(self, state: GenerationState, request: TRequest) -> str:
        llm_messages = self._build_llm_messages(state, request)
        llm = await (
            self._ollama_llm_facade.get_llm_json()
            if self.uses_json_mode
            else self._ollama_llm_facade.get_llm_base()
        )
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise self.exception_cls(EMPTY_RESPONSE_MESSAGE, status_code=502)
        return self._postprocess_raw(raw)

    @staticmethod
    def _conversation_with_answer(state: GenerationState, answer: str) -> list[Message]:
        capped = answer[:MAX_MESSAGE_CONTENT_CHARS]
        return [*state.messages, Message(role=MessageRole.assistant, content=capped)]

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

                raw = await self._invoke(state, request)
                parsed = self._parse_output(raw, request)
                response = self._build_response(state, request, parsed, raw)

                obs["outcome"] = "success"
                self._logger.info(
                    "%s generation completed",
                    self.label.capitalize(),
                    extra=log_extra(
                        user_id=authenticated_user.id,
                        fragments_used=len(state.all_fragments),
                        **self._result_log_extra(parsed),
                    ),
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
                yield self.stream_progress_event(step="processing", message=INITIAL_PROGRESS_MESSAGE)
                state = self._build_state(request, authenticated_user)
                async for progress_event in self._collect_context_with_progress(state):
                    yield progress_event

                yield self.stream_progress_event(
                    step="generation",
                    message=self._generation_progress_message(request),
                )

                raw = await self._invoke(state, request)
                parsed = self._parse_output(raw, request)
                yield self.stream_complete_event(result=self._build_response(state, request, parsed, raw))
                obs["outcome"] = "success"

            except self._known_exceptions as e:
                obs["outcome"] = "known_error"
                self._logger.warning(
                    "Known error during %s stream generation",
                    self.label,
                    extra=log_extra(user_id=authenticated_user.id, error_type=type(e).__name__),
                )
                yield self.stream_error_event(message=str(e), code=type(e).__name__)
            except Exception as e:
                self._logger.exception(
                    "Unexpected error during %s stream generation",
                    self.label,
                    extra=log_extra(user_id=authenticated_user.id, error_type=type(e).__name__),
                )
                yield self.stream_error_event(message=self.unexpected_error_message, code="internal_error")
