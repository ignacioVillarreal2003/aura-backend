import logging
from typing import List
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class OllamaLLMInvoker(OllamaLLMInvokerInterface):
    _RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)
    _MAX_RETRY_ATTEMPTS = 3
    _RETRY_MIN_WAIT = 1.0
    _RETRY_MAX_WAIT = 8.0

    async def call_llm(
            self,
            llm: Runnable,
            llm_input: List[BaseMessage],
    ) -> BaseMessage:
        logger.debug("Invoking LLM", extra={"message_count": len(llm_input)})

        @retry(
            stop=stop_after_attempt(self._MAX_RETRY_ATTEMPTS),
            wait=wait_exponential(min=self._RETRY_MIN_WAIT, max=self._RETRY_MAX_WAIT),
            retry=retry_if_exception_type(self._RETRYABLE_EXCEPTIONS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        async def _invoke_with_retry() -> BaseMessage:
            return await llm.ainvoke(llm_input)

        try:
            response = await _invoke_with_retry()

            if not isinstance(response, BaseMessage):
                raise LLMInvocationError(
                    f"Expected BaseMessage, got {type(response).__name__}"
                )

            logger.debug("LLM invocation successful")
            return response

        except LLMInvocationError:
            raise
        except self._RETRYABLE_EXCEPTIONS as e:
            logger.error(
                "LLM invocation failed after retries",
                extra={"error_type": type(e).__name__, "error_message": str(e)}
            )
            raise LLMInvocationError(
                "El LLM no respondió después de varios intentos. "
                "Por favor, intente nuevamente más tarde."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error during LLM invocation",
                extra={"error_type": type(e).__name__}
            )
            raise LLMInvocationError("The LLM could not process the request.") from e

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
            raise LLMInvocationError("The LLM response has no content.")

        if isinstance(content, list):
            text_parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = " ".join(text_parts).strip()

            if not content:
                logger.warning(
                    "LLM returned list content with no extractable text blocks",
                    extra={"block_count": len(response.content)}
                )

            return content

        if not isinstance(content, str):
            raise LLMInvocationError(
                f"Unexpected content type in LLM response: {type(content).__name__}"
            )

        result = content.strip()

        if not result:
            logger.warning("LLM response content is empty after stripping")

        return result
