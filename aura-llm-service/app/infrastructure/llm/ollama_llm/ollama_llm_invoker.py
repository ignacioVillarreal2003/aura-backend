import logging
import time
from typing import List, Optional
import httpx
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from tenacity import AsyncRetrying, before_sleep_log, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.configuration.metrics import model_name_of, record_llm_usage, usage_tokens
from app.infrastructure.llm.ollama_llm.llm_concurrency import llm_slot
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.llm_payload_logging import log_llm_input, log_llm_output
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker_settings import OllamaLLMInvokerSettings

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
    ConnectionError,
    TimeoutError,
    OSError,
)


class OllamaLLMInvoker(OllamaLLMInvokerInterface):
    def __init__(self, settings: Optional[OllamaLLMInvokerSettings] = None) -> None:
        self._settings = settings or OllamaLLMInvokerSettings()

    async def call_llm(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> BaseMessage:
        logger.debug("Invoking LLM", extra={"message_count": len(llm_input)})
        if self._settings.log_payloads:
            log_llm_input(logger, llm_input, self._settings.log_payload_max_chars)

        response: BaseMessage | None = None
        started = time.perf_counter()
        try:
            async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self._settings.max_retry_attempts),
                    wait=wait_exponential(
                        min=self._settings.retry_min_wait,
                        max=self._settings.retry_max_wait,
                    ),
                    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
                    before_sleep=before_sleep_log(logger, logging.WARNING),
                    reraise=True,
            ):
                with attempt:
                    async with llm_slot():
                        response = await llm.ainvoke(llm_input)

        except LLMInvocationError:
            raise
        except _RETRYABLE_EXCEPTIONS as e:
            logger.error(
                "LLM invocation failed after retries",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
            )
            raise LLMInvocationError(
                "LLM failed to respond after multiple retry attempts. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error during LLM invocation",
                extra={"error_type": type(e).__name__},
            )
            raise LLMInvocationError("LLM could not process the request.") from e

        if not isinstance(response, BaseMessage):
            raise LLMInvocationError(
                f"Expected BaseMessage response, got {type(response).__name__}."
            )

        input_tokens, output_tokens = usage_tokens(response)
        record_llm_usage(
            model=model_name_of(llm),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=time.perf_counter() - started,
        )

        if self._settings.log_payloads:
            content = response.content if isinstance(response.content, str) else str(response.content)
            log_llm_output(logger, content, self._settings.log_payload_max_chars)

        logger.debug("LLM invocation successful")
        return response

    async def call_llm_content(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> str:
        response = await self.call_llm(llm=llm, llm_input=llm_input)
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: BaseMessage) -> str:
        content = getattr(response, "content", None)

        if content is None:
            raise LLMInvocationError("LLM response has no content field.")

        if isinstance(content, list):
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            result = " ".join(text_parts).strip()
            if not result:
                raise LLMInvocationError(
                    "LLM returned a list response with no extractable text blocks."
                )
            return result

        if not isinstance(content, str):
            raise LLMInvocationError(
                f"Unexpected content type in LLM response: {type(content).__name__}."
            )

        result = content.strip()
        if not result:
            raise LLMInvocationError("LLM returned an empty response.")

        return result
