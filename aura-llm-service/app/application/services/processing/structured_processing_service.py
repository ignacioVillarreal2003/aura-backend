import json
import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import AppException, RequestValidationException
from app.application.utils.llm_json_parser import parse_json_object
from app.configuration.tracing import trace_generation
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

_DEFAULT_PARSE_ERROR_MESSAGE = "La respuesta del modelo no tiene el formato JSON esperado."

TRequest = TypeVar("TRequest")
TParsed = TypeVar("TParsed", bound=BaseModel)
TResponse = TypeVar("TResponse")


class StructuredProcessingService(ABC, Generic[TRequest, TParsed, TResponse]):
    label: ClassVar[str]
    exception_cls: ClassVar[type[AppException]]
    parsed_model: ClassVar[type[BaseModel]]
    llm_error_message: ClassVar[str]
    unexpected_error_message: ClassVar[str]
    parse_error_message: ClassVar[str] = _DEFAULT_PARSE_ERROR_MESSAGE

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._known_exceptions: tuple[type[Exception], ...] = (
            RequestValidationException,
            self.exception_cls,
            UnauthorizedException,
        )
        self._logger = logging.getLogger(type(self).__module__)

    @abstractmethod
    def _build_messages(self, request: TRequest, authenticated_user: AuthenticatedUser) -> list[BaseMessage]:
        pass

    def _postprocess(
            self,
            parsed: TParsed,
            request: TRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TResponse:
        return parsed

    def _max_repair_attempts(self, request: TRequest) -> int:
        return 0

    def _build_repair_messages(
            self,
            original_messages: list[BaseMessage],
            malformed_output: str,
            parse_error: str,
    ) -> list[BaseMessage]:
        raise NotImplementedError(
            f"{type(self).__name__} enabled JSON repair but did not implement _build_repair_messages."
        )

    def _request_log_extra(self, request: TRequest, authenticated_user: AuthenticatedUser) -> dict[str, Any]:
        return {"user_id": authenticated_user.id}

    def _result_log_extra(self, result: TResponse) -> dict[str, Any]:
        return {}

    @trace_generation()
    async def _generate(self, request: TRequest, authenticated_user: AuthenticatedUser) -> TResponse:
        log_extra = self._request_log_extra(request, authenticated_user)
        self._logger.info("%s initiated", self.label.capitalize(), extra=log_extra)
        try:
            messages = self._build_messages(request, authenticated_user)
            parsed = await self._run_with_repair(messages, request, authenticated_user.id)
            result = self._postprocess(parsed, request, authenticated_user)
            self._logger.info(
                "%s completed",
                self.label.capitalize(),
                extra={**log_extra, **self._result_log_extra(result)},
            )
            return result
        except self._known_exceptions:
            raise
        except Exception as e:
            self._logger.exception(
                "Unexpected error during %s",
                self.label,
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise self.exception_cls(self.unexpected_error_message, status_code=500) from e

    async def _run_with_repair(
            self,
            messages: list[BaseMessage],
            request: TRequest,
            user_id: int,
    ) -> TParsed:
        raw = await self._call_llm_json(messages, user_id)
        max_attempts = self._max_repair_attempts(request)
        last_error: AppException | None = None

        for attempt in range(max_attempts + 1):
            try:
                parsed = self._parse(raw, user_id)
                if attempt > 0:
                    self._logger.info(
                        "%s JSON repair succeeded",
                        self.label.capitalize(),
                        extra={"user_id": user_id, "attempt": attempt},
                    )
                return parsed
            except self.exception_cls as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                self._logger.warning(
                    "%s JSON malformed; attempting repair",
                    self.label.capitalize(),
                    extra={"user_id": user_id, "attempt": attempt + 1, "max_repair_attempts": max_attempts},
                )
                repair_messages = self._build_repair_messages(messages, raw, str(exc))
                raw = await self._call_llm_json(repair_messages, user_id)

        assert last_error is not None
        raise last_error

    async def _call_llm_json(self, messages: list[BaseMessage], user_id: int) -> str:
        try:
            llm = await self._ollama_llm_facade.get_llm_json()
            return await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=messages)
        except LLMInvocationError as e:
            self._logger.warning(
                "LLM invocation failed during %s",
                self.label,
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise self.exception_cls(self.llm_error_message, status_code=502) from e
        except self.exception_cls:
            raise
        except Exception as e:
            self._logger.exception(
                "Unexpected LLM error during %s",
                self.label,
                extra={"user_id": user_id, "error_type": type(e).__name__},
            )
            raise self.exception_cls(self.llm_error_message, status_code=502) from e

    def _parse(self, raw: str, user_id: int) -> TParsed:
        try:
            data = parse_json_object(raw)
            return self.parsed_model.model_validate(data)  # type: ignore[return-value]
        except (ValidationError, json.JSONDecodeError, TypeError) as e:
            self._logger.warning(
                "Failed to parse %s JSON from LLM",
                self.label,
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            raise self.exception_cls(self.parse_error_message, status_code=502) from e

    def _truncate(self, text: str, max_chars: int, user_id: int, what: str) -> str:
        if len(text) <= max_chars:
            return text
        self._logger.info(
            "Truncating %s for %s",
            what,
            self.label,
            extra={"original_len": len(text), "max_chars": max_chars, "user_id": user_id},
        )
        return text[:max_chars]
