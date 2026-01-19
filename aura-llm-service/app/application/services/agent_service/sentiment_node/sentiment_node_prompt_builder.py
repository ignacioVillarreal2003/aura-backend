import logging
from typing import List

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    BaseMessage
)

logger = logging.getLogger(__name__)


class SentimentNodePromptBuilder:
    def build_prompt(self,
                     system_prompt: str,
                     input_text: str) -> List[BaseMessage]:
        logger.info(
            "Starting sentiment_node prompt build"
        )

        prompt_messages: List[BaseMessage] = []

        prompt_messages.append(
            self._build_system_message(system_prompt)
        )

        prompt_messages.append(
            self._build_sentiment_input_message(input_text)
        )

        logger.info(
            "Sentiment prompt built successfully"
        )

        return prompt_messages

    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        logger.debug(
            "Building system message"
        )

        return SystemMessage(
            content=system_prompt
        )

    @staticmethod
    def _build_sentiment_input_message(input_text: str) -> HumanMessage:
        logger.debug(
            "Building sentiment_node input message"
        )

        return HumanMessage(
            content=(
                "Analiza el siguiente texto y clasifica su sentimiento:\n\n"
                f"{input_text}"
            )
        )
