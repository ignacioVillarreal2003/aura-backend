import logging
import time
from collections.abc import AsyncIterator
from typing import Any, List, Optional
import httpx
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from tenacity import AsyncRetrying, before_sleep_log, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.configuration.metrics import model_name_of, record_llm_usage, usage_tokens
from app.infrastructure.llm.ollama_llm.llm_concurrency import llm_slot
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)
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

_SKIP_STREAM_BLOCK_TYPES = frozenset({
    "reasoning",
    "tool_call",
    "tool_call_chunk",
    "invalid_tool_call",
    "server_tool_call",
    "image",
    "image_url",
    "audio",
    "refusal",
})

_STREAM_EMPTY = object()


class OllamaLLMStreamingInvoker(OllamaLLMStreamingInvokerInterface):
    def __init__(self, settings: Optional[OllamaLLMInvokerSettings] = None) -> None:
        self._settings = settings or OllamaLLMInvokerSettings()

    async def stream_llm_content(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> AsyncIterator[str]:
        logger.debug("Starting LLM stream", extra={"message_count": len(llm_input)})
        if self._settings.log_payloads:
            log_llm_input(logger, llm_input, self._settings.log_payload_max_chars)

        started = time.perf_counter()
        gen: AsyncIterator[Any] | None = None
        first_chunk: Any = _STREAM_EMPTY

        async with llm_slot():
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
                        if gen is not None:
                            await gen.aclose()
                        gen = llm.astream(llm_input)
                        first_chunk = await anext(gen, _STREAM_EMPTY)

            except LLMInvocationError:
                raise
            except _RETRYABLE_EXCEPTIONS as e:
                logger.error(
                    "LLM stream failed after retries",
                    extra={"error_type": type(e).__name__, "error_message": str(e)},
                )
                raise LLMInvocationError(
                    "LLM failed to respond after multiple retry attempts. Please try again later."
                ) from e
            except Exception as e:
                logger.exception(
                    "Unexpected error while establishing LLM stream",
                    extra={"error_type": type(e).__name__},
                )
                raise LLMInvocationError("LLM could not process the streaming request.") from e

            if first_chunk is _STREAM_EMPTY:
                logger.debug("LLM returned an empty stream")
                return

            total_chars = 0
            payload_buffer: list[str] = []
            payload_buffered_chars = 0
            usage: tuple[Optional[int], Optional[int]] = (None, None)
            try:
                usage = self._merge_usage(usage, first_chunk)
                text = self._chunk_to_text(first_chunk)
                if text:
                    total_chars += len(text)
                    if total_chars > self._settings.max_stream_response_chars:
                        raise LLMInvocationError("Streaming response exceeded maximum allowed size.")
                    if self._settings.log_payloads and payload_buffered_chars < self._settings.log_payload_max_chars:
                        payload_buffer.append(text)
                        payload_buffered_chars += len(text)
                    yield text

                async for chunk in gen:
                    usage = self._merge_usage(usage, chunk)
                    text = self._chunk_to_text(chunk)
                    if text:
                        total_chars += len(text)
                        if total_chars > self._settings.max_stream_response_chars:
                            raise LLMInvocationError("Streaming response exceeded maximum allowed size.")
                        if self._settings.log_payloads and payload_buffered_chars < self._settings.log_payload_max_chars:
                            payload_buffer.append(text)
                            payload_buffered_chars += len(text)
                        yield text

            except LLMInvocationError:
                raise
            except _RETRYABLE_EXCEPTIONS as e:
                logger.error(
                    "LLM stream interrupted mid-stream — cannot retry",
                    extra={"error_type": type(e).__name__, "error_message": str(e)},
                )
                raise LLMInvocationError("LLM connection was interrupted mid-stream.") from e
            except Exception as e:
                logger.exception(
                    "Unexpected error during LLM streaming",
                    extra={"error_type": type(e).__name__},
                )
                raise LLMInvocationError("LLM could not process the streaming request.") from e
            finally:
                record_llm_usage(
                    model=model_name_of(llm),
                    input_tokens=usage[0],
                    output_tokens=usage[1],
                    duration_seconds=time.perf_counter() - started,
                )
                if gen is not None:
                    await gen.aclose()

            if self._settings.log_payloads:
                log_llm_output(logger, "".join(payload_buffer), self._settings.log_payload_max_chars)

            logger.debug("LLM streaming completed successfully", extra={"total_chars": total_chars})

    @staticmethod
    def _merge_usage(
            current: tuple[Optional[int], Optional[int]],
            chunk: Any,
    ) -> tuple[Optional[int], Optional[int]]:
        chunk_in, chunk_out = usage_tokens(chunk)
        cur_in, cur_out = current
        merged_in = chunk_in if chunk_in is not None and (cur_in is None or chunk_in > cur_in) else cur_in
        merged_out = chunk_out if chunk_out is not None and (cur_out is None or chunk_out > cur_out) else cur_out
        return merged_in, merged_out

    @staticmethod
    def _chunk_to_text(chunk: Any) -> str:
        content = getattr(chunk, "content", None)

        if isinstance(content, str):
            return content

        if not content:
            return ""

        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                    continue
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype in _SKIP_STREAM_BLOCK_TYPES:
                    continue
                text_val = block.get("text")
                if isinstance(text_val, str) and text_val:
                    parts.append(text_val)
                    continue
                if btype in (None, "text", "text_delta"):
                    alt = block.get("content")
                    if isinstance(alt, str) and alt:
                        parts.append(alt)
            return "".join(parts)

        return ""
