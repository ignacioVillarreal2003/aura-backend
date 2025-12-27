import logging
import re
from typing import Dict, Any, List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.application.nodes.interfaces.node_interface import NodeInterface
from app.domain.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


class SentimentNode(NodeInterface):
    SYSTEM_PROMPT: str = (
        "Eres un experto clasificador de sentimientos. "
        "Tu tarea es analizar el mensaje del usuario y clasificar su sentimiento emocional. "
        "Debes responder ÚNICAMENTE con una de estas tres palabras: positive, negative, neutral. "
        "No incluyas explicaciones, puntuación adicional ni texto extra."
    )
    USER_PROMPT_TEMPLATE: str = (
        "Analiza el siguiente mensaje y clasifica su sentimiento:\n\n"
        '"{message}"'
    )

    def __init__(self,
                 llm_configurator: LLMConfiguratorInterface) -> None:
        self._llm_configurator = llm_configurator
        self._llm: Runnable = self._llm_configurator.get_llm_base()

    async def process(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing SentimentNode")

        last_message = self._extract_last_message(state)
        prompt = self._build_prompt(last_message.content)

        logger.debug("Invoking LLM for sentiment classification")

        try:
            sentiment = await self._classify_sentiment(prompt)

            logger.info("SentimentNode processed successfully")
            return {
                "sentiment": sentiment
            }

        except Exception:
            logger.exception("LLM invocation failed for sentiment classification")
            raise

    @staticmethod
    def _extract_last_message(state: AgentState) -> BaseMessage:
        messages = state.get("messages")

        if messages is None:
            raise ValueError("State must contain 'messages' field")

        if not isinstance(messages, list):
            raise ValueError(
                f"Messages must be a list, got {type(messages).__name__}"
            )

        if len(messages) == 0:
            raise ValueError("Messages list cannot be empty")

        last_message = messages[-1]

        if not isinstance(last_message, BaseMessage):
            raise ValueError(
                f"Last message must be BaseMessage, got {type(last_message).__name__}"
            )

        return last_message

    def _build_prompt(self,
                      message: str) -> List[BaseMessage]:
        return [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=self.USER_PROMPT_TEMPLATE.format(message=message))
        ]

    async def _classify_sentiment(self,
                                  prompt: List[BaseMessage]) -> Sentiment:
        try:
            response = await self._llm.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type: {type(response)}")

            sentiment = self._parse_sentiment_response(response.content)
            logger.debug(f"Parsed sentiment: {sentiment}")
            return sentiment

        except Exception:
            logger.exception("LLM classification failed")
            raise

    @staticmethod
    def _parse_sentiment_response(response: str) -> Sentiment:
        cleaned = (response or "").strip()
        logger.debug(f"Parsing sentiment from LLM response: {cleaned!r}")

        normalized = cleaned.lower()

        for s in Sentiment:
            if normalized == s.value.lower():
                return s

        m = re.search(r'\b(positive|negative|neutral)\b', normalized, re.IGNORECASE)
        if m:
            word = m.group(1).lower()
            for s in Sentiment:
                if s.value.lower() == word:
                    return s

        logger.warning(f"Could not parse sentiment from response: {response}")
        return Sentiment.neutral


def create_sentiment_node(llm_configurator: LLMConfiguratorInterface) -> SentimentNode:
    return SentimentNode(llm_configurator)
