import logging
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class SentimentNodePromptBuilder:
    def build_prompt(self, system_prompt: str, input_text: str) -> List[BaseMessage]:
        logger.debug("Building sentiment prompt")

        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "Analyze the following text and classify its sentiment:\n\n"
                    f"{input_text}"
                )
            )
        ]

        logger.debug("Sentiment prompt built successfully")
        return messages
