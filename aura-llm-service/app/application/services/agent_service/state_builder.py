import logging
from typing import List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.domain.constants.message_role import MessageRole
from app.domain.constants.sentimient import Sentiment
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class StateBuilder:
    def build_initial_state(self,
                            request: AgentRequest,
                            default_sentiment: Sentiment = Sentiment.neutral) -> Dict[str, Any]:
        logger.debug(
            "Building initial state",
            extra={
                "has_history": request.history_messages is not None,
                "history_count": len(request.history_messages) if request.history_messages else 0,
                "default_sentiment": default_sentiment.value
            }
        )

        messages: List[BaseMessage] = []

        if request.history_messages:
            messages = self._convert_history_messages(request.messages)

        messages.append(
            HumanMessage(
                content=request.message
            )
        )

        state = {
            "messages": messages,
            "sentiment": default_sentiment.value
        }

        logger.debug(
            "Initial state built",
            extra={
                "total_messages": len(messages),
                "sentiment": default_sentiment.value
            }
        )

        return state

    @staticmethod
    def _convert_history_messages(history_messages: List[Message]) -> List[BaseMessage]:
        history: List[BaseMessage] = []

        for idx, msg in enumerate(history_messages):
            try:
                if msg.role == MessageRole.human or msg.role == "user":
                    history.append(
                        HumanMessage(
                            content=msg.content
                        )
                    )
                elif msg.role == MessageRole.assistant or msg.role == "assistant":
                    history.append(
                        AIMessage(
                            content=msg.content
                        )
                    )
                else:
                    logger.warning(
                        "Unknown message role in history, skipping",
                        extra={
                            "index": idx,
                            "role": msg.role
                        }
                    )
            except Exception as e:
                logger.error(
                    "Error converting history message, skipping",
                    extra={
                        "index": idx,
                        "error": str(e)
                    },
                    exc_info=True
                )
                continue

        logger.debug(
            "History messages converted",
            extra={
                "original_count": len(history_messages),
                "converted_count": len(history)
            }
        )

        return history
