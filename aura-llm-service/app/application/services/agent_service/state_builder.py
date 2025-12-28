from typing import List, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage

from app.domain.constants.sentimient import Sentiment
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message


class StateBuilder:
    @staticmethod
    def build_initial_state(
            request: AgentRequest,
            default_sentiment: Sentiment = Sentiment.neutral
    ) -> Dict[str, Any]:
        messages = []

        if request.messages:
            messages = StateBuilder._convert_history_messages(request.messages)

        messages.append(HumanMessage(content=request.message))

        return {
            "messages": messages,
            "sentiment": default_sentiment.value
        }

    @staticmethod
    def _convert_history_messages(messages: List[Message]) -> List[BaseMessage]:
        history: List[BaseMessage] = []

        for msg in messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history.append(AIMessage(content=msg.content))
            else:
                logger.warning(
                    f"Unknown message role: {msg.role}, skipping"
                )

        return history