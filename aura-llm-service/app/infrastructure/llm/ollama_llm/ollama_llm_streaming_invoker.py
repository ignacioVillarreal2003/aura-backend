import logging
from collections.abc import AsyncIterator
from typing import Any, List, Optional

import httpx
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from tenacity import AsyncRetrying, before_sleep_log, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)
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

        # Phase 1 — establish the stream with tenacity retries.
        # Cannot retry once chunks are flowing, so we get the first chunk here
        # and then consume the rest outside the retry loop.
        gen: AsyncIterator[Any] | None = None
        first_chunk: Any = _STREAM_EMPTY

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

        # Phase 2 — yield chunks; no retry is possible once streaming has started.
        total_chars = 0
        try:
            text = self._chunk_to_text(first_chunk)
            if text:
                total_chars += len(text)
                if total_chars > self._settings.max_stream_response_chars:
                    raise LLMInvocationError("Streaming response exceeded maximum allowed size.")
                yield text

            async for chunk in gen:
                text = self._chunk_to_text(chunk)
                if text:
                    total_chars += len(text)
                    if total_chars > self._settings.max_stream_response_chars:
                        raise LLMInvocationError("Streaming response exceeded maximum allowed size.")
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

        logger.debug("LLM streaming completed successfully", extra={"total_chars": total_chars})

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
