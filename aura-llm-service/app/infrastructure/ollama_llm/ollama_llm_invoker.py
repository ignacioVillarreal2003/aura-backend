import logging
from typing import List
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.infrastructure.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class OllamaLLMInvoker(OllamaLLMInvokerInterface):
    async def call_llm(self,
                       llm: Runnable,
                       llm_input: List[BaseMessage]) -> BaseMessage:
        logger.debug("Invoking LLM")

        try:
            response = await llm.ainvoke(llm_input)

            if not isinstance(response, BaseMessage):
                logger.error(
                    "LLM returned unexpected response type",
                    extra={
                        "expected_type": "BaseMessage",
                        "received_type": type(response).__name__
                    }
                )
                raise LLMInvocationError(f"Expected BaseMessage, received {type(response).__name__}")

            logger.info("LLM invocation successful")
            return response

        except LLMInvocationError:
            raise
        except Exception as e:
            logger.exception(
                "Critical error during LLM invocation",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise LLMInvocationError("The LLM failed to process the request") from e

    async def call_llm_content(self,
                               llm: Runnable,
                               llm_input: List[BaseMessage]) -> str:
        response = await self.call_llm(
            llm=llm,
            llm_input=llm_input
        )
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: BaseMessage) -> str:
        content = getattr(response, "content", None)

        if content is None:
            logger.error(
                "LLM response has no content attribute",
                extra={"response_type": type(response).__name__}
            )
            raise LLMInvocationError("LLM response has no content attribute")

        if not isinstance(content, str):
            logger.error(
                "LLM response content is not a string",
                extra={
                    "expected_type": "str",
                    "received_type": type(content).__name__
                }
            )
            raise LLMInvocationError(f"Expected response content to be str, got {type(content).__name__}")

        content = content.strip()

        if not content:
            logger.warning("LLM response content is empty after stripping")

        return content