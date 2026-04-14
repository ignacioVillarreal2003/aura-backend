import logging
from collections.abc import AsyncIterator
from typing import Any, List

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)

# Content block types we must not surface as user-visible streamed text.
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


class OllamaLLMStreamingInvoker(OllamaLLMStreamingInvokerInterface):
    async def stream_llm_content(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> AsyncIterator[str]:
        logger.debug("Streaming LLM", extra={"message_count": len(llm_input)})

        try:
            async for chunk in llm.astream(llm_input):
                text = self._chunk_to_text(chunk)
                if text:
                    yield text
        except LLMInvocationError:
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(
                "LLM streaming failed (network)",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
            )
            raise LLMInvocationError(
                "El LLM no respondió después de varios intentos. "
                "Por favor, intente nuevamente más tarde."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error during LLM streaming",
                extra={"error_type": type(e).__name__},
            )
            raise LLMInvocationError("The LLM could not process the request.") from e

        logger.debug("LLM streaming finished")

    @staticmethod
    def _chunk_to_text(chunk: Any) -> str:
        """Extract token/delta text from astream chunks (shape varies by provider/LC version)."""
        if isinstance(chunk, (tuple, list)) and chunk:
            chunk = chunk[0]

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
