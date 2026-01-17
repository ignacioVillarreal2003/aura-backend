import logging
from typing import List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.constants.sentimient import Sentiment
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentStateBuilder:
    def build_agent_state(self,
                          request: AgentRequest) -> AgentState:
        logger.debug(
            "Building agent state",
            extra={
                "messages": request.messages
            }
        )

        messages: List[BaseMessage] = []

        if request.messages is not None:
            messages = self._convert_messages(request.messages)

        agent_state: AgentState = AgentState(
            messages=messages,
            sentiment=Sentiment.NEUTRAL
        )

        logger.debug(
            "Agent state built",
            extra={
                "agent_state": agent_state
            }
        )

        return agent_state

    @staticmethod
    def _convert_messages(messages: Optional[list[Message]]) -> List[BaseMessage]:
        history_messages: List[BaseMessage] = []

        for index, message in enumerate(messages):
            try:
                if message.role == MessageRole.human:
                    history_messages.append(
                        HumanMessage(
                            content=message.content
                        )
                    )
                elif message.role == MessageRole.assistant:
                    history_messages.append(
                        AIMessage(
                            content=message.content
                        )
                    )
                else:
                    logger.warning(
                        "Unknown message role in history, skipping",
                        extra={
                            "index": index,
                            "message": message
                        }
                    )
            except Exception as e:
                logger.error(
                    "Error converting history message, skipping",
                    extra={
                        "index": index,
                        "error": str(e)
                    },
                    exc_info=True
                )
                continue

        logger.debug(
            "History messages converted",
            extra={
                "history_messages": history_messages
            }
        )

        return history_messages
