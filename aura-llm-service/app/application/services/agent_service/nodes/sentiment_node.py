from typing import Optional, Dict, Any, List

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.runnables import Runnable

from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.services.agent_service.sentiment_configuration import SentimentConfig
from app.domain.agent_state.agent_state import AgentState
from app.domain.constants.sentimient import Sentiment


class SentimentNode:
    def __init__(
            self,
            llm_facade: LLMFacadeInterface,
            config: Optional[SentimentConfig] = None
    ):
        self._llm_configurator = llm_facade
        self._config = config or SentimentConfig()

        # LLM initialized lazily
        self._llm: Optional[Runnable] = None

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        return await self.process(state)

    async def process(self, state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing sentiment analysis")

        await self._ensure_llm_initialized()

        last_message = self._extract_last_message(state)

        prompt = self._build_prompt(last_message.content)

        try:
            sentiment = await self._classify_sentiment(prompt)

            logger.info(f"Sentiment analyzed: {sentiment.value}")

            return {"sentiment": sentiment.value}

        except Exception:
            logger.exception("Sentiment analysis failed")
            return {"sentiment": Sentiment.neutral.value}

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is None:
            self._llm = await self._llm_configurator.get_llm_base()

    @staticmethod
    def _extract_last_message(state: AgentState) -> BaseMessage:
        messages = state.get("messages")

        if not messages or len(messages) == 0:
            raise ValueError("State must contain at least one message")

        last_message = messages[-1]

        if not isinstance(last_message, BaseMessage):
            raise ValueError(
                f"Last message must be BaseMessage, got {type(last_message)}"
            )

        return last_message

    def _build_prompt(self, message: str) -> List[BaseMessage]:
        return [
            SystemMessage(content=self._config.system_prompt),
            HumanMessage(
                content=self._config.user_prompt_template.format(message=message)
            )
        ]

    async def _classify_sentiment(
            self,
            prompt: List[BaseMessage]
    ) -> Sentiment:
        if self._llm is None:
            raise RuntimeError("LLM not initialized")

        try:
            response = await self._llm.ainvoke(prompt)

            if not isinstance(response, BaseMessage):
                raise TypeError(f"LLM returned invalid type: {type(response)}")

            sentiment = self._parse_sentiment_response(response.content)
            logger.debug(f"Parsed sentiment: {sentiment.value}")

            return sentiment

        except Exception:
            logger.exception("LLM classification failed")
            raise

    @staticmethod
    def _parse_sentiment_response(response: str) -> Sentiment:
        import re

        cleaned = (response or "").strip().lower()

        logger.debug(f"Parsing sentiment from: {cleaned!r}")

        for s in Sentiment:
            if cleaned == s.value.lower():
                return s

        pattern = r'\b(positive|negative|neutral)\b'
        match = re.search(pattern, cleaned, re.IGNORECASE)

        if match:
            word = match.group(1).lower()
            for s in Sentiment:
                if s.value.lower() == word:
                    return s

        logger.warning(f"Could not parse sentiment, defaulting to neutral")
        return Sentiment.neutral