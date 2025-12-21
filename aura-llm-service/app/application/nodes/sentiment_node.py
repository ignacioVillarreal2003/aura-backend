import logging
import re
from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.ollama_configurator.ollama_configurator import OllamaConfigurator
from app.application.graph.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment

logger = logging.getLogger(__name__)


class SentimentNodeConfig:
    def __init__(self,
                 use_system_prompt: bool = True,
                 max_tokens: int = 10,
                 temperature: float = 0.0,
                 fallback_sentiment: Sentiment = Sentiment.neutral):
        self.use_system_prompt = use_system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.fallback_sentiment = fallback_sentiment


class SentimentNode:
    SYSTEM_PROMPT: str = (
        "Eres un experto clasificador de sentimientos. "
        "Tu tarea es analizar el mensaje del usuario y clasificar su sentimiento emocional. "
        "Debes responder ÚNICAMENTE con una de estas tres palabras: POSITIVE, NEUTRAL, NEGATIVE. "
        "No incluyas explicaciones, puntuación adicional ni texto extra."
    )

    USER_PROMPT_TEMPLATE: str = (
        "Analiza el siguiente mensaje y clasifica su sentimiento:\n\n"
        '"{message}"\n\n'
        "Responde solo con: POSITIVE, NEUTRAL o NEGATIVE"
    )

    SENTIMENT_KEYWORDS: Dict[Sentiment, List[str]] = {
        Sentiment.positive: ["positivo", "positive", "feliz", "contento", "alegre"],
        Sentiment.negative: ["negativo", "negative", "enojado", "triste", "molesto"],
        Sentiment.neutral: ["neutral", "normal", "ninguno"]
    }

    def __init__(self,
                 ollama_configurator: OllamaConfigurator,
                 config: Optional[SentimentNodeConfig] = None):
        self.ollama_configurator = ollama_configurator
        self.config = config or SentimentNodeConfig()

        self.llm: Runnable = self.ollama_configurator.get_llm_base()

        logger.info("SentimentNode initialized")

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        return await self.analyze(state)

    async def analyze(self,
                      state: AgentState) -> Dict[str, Any]:
        logger.debug("Starting sentiment analysis")

        last_message = self._extract_last_message(state)

        message_preview = last_message.content[:50]
        if len(last_message.content) > 50:
            message_preview += "..."

        logger.debug("Analyzing message")

        prompt = self._build_prompt(last_message.content)

        try:
            sentiment = await self._classify_sentiment(prompt)

            logger.info("Sentiment classified successfully")

        except Exception:
            logger.error("Sentiment classification failed")
            sentiment = self.config.fallback_sentiment

        return {"sentiment": sentiment.value}

    def _extract_last_message(self,
                              state: AgentState) -> BaseMessage:
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
                      message_content: str) -> List[BaseMessage] | str:
        if self.config.use_system_prompt:
            return [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(
                    content=self.USER_PROMPT_TEMPLATE.format(
                        message=message_content
                    )
                )
            ]
        else:
            return self.USER_PROMPT_TEMPLATE.format(message=message_content)

    async def _classify_sentiment(self,
                                  prompt: List[BaseMessage] | str) -> Sentiment:
        logger.debug("Invoking LLM for sentiment classification")

        try:
            response = await self.llm.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError("LLM returned invalid type")

            sentiment = self._parse_sentiment_response(response.content)

            logger.debug("LLM classification successful")

            return sentiment

        except Exception:
            logger.error("LLM classification failed")
            raise

    def _parse_sentiment_response(self,
                                  response: str) -> Sentiment:
        cleaned = response.strip().upper()

        logger.debug(f"Parsing sentiment from response")

        for sentiment in Sentiment:
            if sentiment.value in cleaned:
                return sentiment

        for sentiment, keywords in self.SENTIMENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.upper() in cleaned:
                    logger.debug(f"Matched sentiment via keyword: '{keyword}' -> {sentiment.value}")
                    return sentiment

        match = re.search(
            r'\b(positive|negative|neutral|positivo|negativo)\b',
            cleaned,
            re.IGNORECASE
        )

        if match:
            word = match.group(1).upper()
            if word == "positive":
                return Sentiment.positive
            elif word == "negative":
                return Sentiment.negative
            elif word in [s.value for s in Sentiment]:
                return Sentiment(word)

        logger.warning(
            f"Could not parse sentiment from response: '{response}', "
            f"using fallback: {self.config.fallback_sentiment.value}"
        )

        return self.config.fallback_sentiment


def create_sentiment_node(ollama_configurator: OllamaConfigurator,
                          config: Optional[SentimentNodeConfig] = None) -> SentimentNode:
    return SentimentNode(ollama_configurator, config)


async def sentiment_node(state: AgentState,
                         ollama_configurator: OllamaConfigurator) -> Dict[str, Any]:
    node = SentimentNode(ollama_configurator)
    return await node(state)
