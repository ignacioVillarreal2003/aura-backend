import logging
import re
from typing import Optional, Dict, Any, List
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.sentiment_configuration import SentimentConfiguration
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class SentimentNode:
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 configuration: Optional[SentimentConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._configuration = configuration or SentimentConfiguration()

        self._llm: Optional[Runnable] = None
        self._llm_initialization_failed = False

        logger.debug("SentimentNode initialized")

    async def __call__(self,
                       state: AgentState) -> Dict[str, Any]:
        return await self.process(state)

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing sentiment analysis")

        try:
            await self._ensure_llm_initialized()

            last_message = self._extract_last_message(state)

            prompt = self._build_prompt(last_message.content)

            sentiment = await self._classify_sentiment(prompt)

            logger.info(f"Sentiment analyzed: {sentiment.value}")

            return {
                "sentiment": sentiment.value
            }

        except Exception as e:
            logger.error(
                "Sentiment analysis failed, defaulting to neutral",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            return {
                "sentiment": Sentiment.neutral.value
            }

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return

        if self._llm_initialization_failed:
            raise RuntimeError("LLM initialization failed previously")

        try:
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for sentiment analysis")
        except Exception as e:
            self._llm_initialization_failed = True
            logger.error("Failed to initialize LLM", exc_info=True)
            raise RuntimeError("Failed to initialize LLM for sentiment analysis") from e

    @staticmethod
    def _extract_last_message(state: AgentState) -> BaseMessage:
        messages = state.get("messages")

        if not messages or len(messages) == 0:
            raise ValueError("State must contain at least one message for sentiment analysis")

        last_message = messages[-1]

        if not isinstance(last_message, BaseMessage):
            raise ValueError(
                f"Last message must be BaseMessage, got {type(last_message)}"
            )

        return last_message

    def _build_prompt(self,
                      message: str) -> List[BaseMessage]:
        return [
            SystemMessage(
                content=self._configuration.system_prompt
            ),
            HumanMessage(
                content=self._configuration.custom_user_template.format(
                    message=message
                )
            )
        ]

    async def _classify_sentiment(self,
                                  prompt: List[BaseMessage]) -> Sentiment:
        if self._llm is None:
            raise RuntimeError("LLM not initialized")

        try:
            response = await self._llm.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type: {type(response)}")

            sentiment = self._parse_sentiment_response(response.content)
            logger.debug(f"Parsed sentiment: {sentiment.value}")

            return sentiment

        except Exception as e:
            logger.exception("Sentiment classification failed")
            raise RuntimeError("Failed to classify sentiment") from e

    @staticmethod
    def _parse_sentiment_response(response: str) -> Sentiment:
        cleaned = (response or "").strip().lower()

        logger.debug(f"Parsing sentiment from response: {cleaned!r}")

        for sentiment in Sentiment:
            if cleaned == sentiment.value.lower():
                return sentiment

        pattern = r'\b(positive|negative|neutral)\b'
        match = re.search(pattern, cleaned, re.IGNORECASE)

        if match:
            word = match.group(1).lower()
            for sentiment in Sentiment:
                if sentiment.value.lower() == word:
                    return sentiment

        logger.warning(
            f"Could not parse sentiment from: {cleaned!r}, defaulting to neutral"
        )
        return Sentiment.neutral
