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
        content = getattr(chunk, "content", None)
        if content is None:
            return ""

        if isinstance(content, list):
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            return "".join(text_parts)

        if isinstance(content, str):
            return content

        return ""
