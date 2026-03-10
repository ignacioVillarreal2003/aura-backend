import logging
from typing import List, Optional

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    BaseMessage
)

logger = logging.getLogger(__name__)


class AgentNodePromptBuilder:
    def build_prompt(
            self,
            system_prompt: str,
            sentiment_instruction: str,
            history_messages: Optional[List[BaseMessage]]
    ) -> List[BaseMessage]:
        logger.info(
            "Starting sentiment_node prompt build"
        )

        prompt_messages: List[BaseMessage] = []

        prompt_messages.append(
            self._build_system_message(system_prompt)
        )

        if history_messages is not None:
            prompt_messages.extend(
                history_messages
            )

        prompt_messages.append(
            self._build_sentiment_instruction_message(sentiment_instruction)
        )

        logger.info(
            "Sentiment prompt built successfully"
        )

        return prompt_messages

    @staticmethod
    def _build_system_message(
            system_prompt: str
    ) -> SystemMessage:
        logger.debug("Building system message")
        return SystemMessage(
            content=system_prompt
        )

    @staticmethod
    def _build_sentiment_instruction_message(
            sentiment_instruction: str
    ) -> HumanMessage:
        logger.debug("Building sentiment instruction message")
        return HumanMessage(
            content=sentiment_instruction
        )
