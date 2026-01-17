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
            "Starting sentiment_node prompt build",
            extra={
                "system_prompt": system_prompt,
                "input_text": input_text
            }
        )

        prompt_messages: List[BaseMessage] = []

        prompt_messages.append(
            self._build_system_message(system_prompt)
        )

        prompt_messages.append(
            self._build_sentiment_input_message(input_text)
        )

        logger.info(
            "Sentiment prompt built successfully",
            extra={
                "prompt_messages": prompt_messages
            }
        )

        return prompt_messages

    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        logger.debug(
            "Building system message",
            extra={
                "system_prompt": system_prompt
            }
        )

        return SystemMessage(
            content=system_prompt
        )

    @staticmethod
    def _build_sentiment_input_message(input_text: str) -> HumanMessage:
        logger.debug(
            "Building sentiment_node input message",
            extra={
                "input_text": input_text
            }
        )

        return HumanMessage(
            content=(
                "Analiza el siguiente texto y clasifica su sentimiento:\n\n"
                f"{input_text}"
            )
        )
