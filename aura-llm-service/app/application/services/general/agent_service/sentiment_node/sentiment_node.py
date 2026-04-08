import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.application.services.general.agent_service.agent_state.agent_state import AgentState
from app.application.services.general.agent_service.constants.sentimient import Sentiment
from app.application.services.general.agent_service.sentiment_node.sentiment_node_configuration import (
    SentimentNodeConfiguration
)
from app.application.services.general.agent_service.sentiment_node.sentiment_node_prompt_builder import (
    SentimentNodePromptBuilder
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class SentimentNode:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            configuration: Optional[SentimentNodeConfiguration] = None
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._configuration = configuration or SentimentNodeConfiguration()
        self._prompt_builder = SentimentNodePromptBuilder()

        self._llm: Optional[Runnable] = None
        self._llm_initialization_failed: bool = False

        logger.debug("SentimentNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing sentiment analysis")

        try:
            await self._ensure_llm_initialized()
            last_message = self._extract_last_message(agent_state)
            prompt = self._build_prompt(last_message.content)
            sentiment = await self._classify_sentiment(prompt)

            logger.info("Sentiment analyzed", extra={"sentiment": sentiment.value})
            return {"sentiment": sentiment.value}

        except Exception as e:
            logger.error(
                "Sentiment analysis failed — defaulting to NEUTRAL",
                extra={"error_type": type(e).__name__, "error": str(e)},
                exc_info=True
            )
            return {"sentiment": Sentiment.neutral.value}

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return

        if self._llm_initialization_failed:
            raise RuntimeError("LLM initialization previously failed — not retrying")

        try:
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for sentiment analysis")
        except Exception as e:
            self._llm_initialization_failed = True
            logger.error("Failed to initialize LLM for sentiment analysis", exc_info=True)
            raise RuntimeError("Failed to initialize LLM for sentiment analysis") from e

    @staticmethod
    def _extract_last_message(agent_state: AgentState) -> BaseMessage:
        messages = agent_state.get("messages")
        if not messages:
            raise ValueError("State must contain at least one message for sentiment analysis")

        last_message = messages[-1]
        if not isinstance(last_message, BaseMessage):
            raise ValueError(
                f"Last message must be a BaseMessage, got {type(last_message).__name__}"
            )
        return last_message

    def _build_prompt(self, last_message_content: str) -> List[BaseMessage]:
        return self._prompt_builder.build_prompt(
            system_prompt=self._configuration.system_prompt,
            input_text=last_message_content
        )

    async def _classify_sentiment(self, prompt: List[BaseMessage]) -> Sentiment:
        if self._llm is None:
            raise RuntimeError("LLM not initialized")

        try:
            response = await self._llm.ainvoke(prompt)
            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned unexpected type: {type(response).__name__}")

            sentiment = self._parse_sentiment_response(response.content)
            logger.debug("Sentiment parsed", extra={"sentiment": sentiment.value})
            return sentiment

        except Exception as e:
            logger.exception("Sentiment classification failed")
            raise RuntimeError("Failed to classify sentiment") from e

    @staticmethod
    def _parse_sentiment_response(response: str) -> Sentiment:
        cleaned = (response or "").strip().lower()
        logger.debug("Parsing sentiment from response", extra={"response": cleaned})

        for sentiment in Sentiment:
            if cleaned == sentiment.value.lower():
                return sentiment

        pattern = r"\b(positive|negative|neutral)\b"
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            for sentiment in Sentiment:
                if sentiment.value.lower() == word:
                    return sentiment

        logger.warning(
            "Could not parse sentiment from response — defaulting to NEUTRAL",
            extra={"response": cleaned}
        )
        return Sentiment.neutral
