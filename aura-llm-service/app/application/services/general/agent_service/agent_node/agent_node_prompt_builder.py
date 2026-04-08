import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class AgentNodePromptBuilder:
    def build_prompt(
            self,
            system_prompt: str,
            sentiment_instruction: str,
            history_messages: Optional[List[BaseMessage]]
    ) -> List[BaseMessage]:
        logger.debug("Building agent node prompt")

        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]

        if history_messages:
            messages.extend(history_messages)

        messages.append(HumanMessage(content=sentiment_instruction))

        logger.debug(
            "Agent node prompt built successfully",
            extra={"total_messages": len(messages)}
        )
        return messages
