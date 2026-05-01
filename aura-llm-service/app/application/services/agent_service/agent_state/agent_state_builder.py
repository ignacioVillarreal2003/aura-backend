import logging
from typing import List, Optional
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.constants.query_intent import QueryIntent
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.agent.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentStateBuilder:
    def build_agent_state(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AgentState:
        logger.debug(
            "Building agent state",
            extra={"message_count": len(agent_request.messages) if agent_request.messages else 0}
        )

        messages: List[BaseMessage] = []
        if agent_request.messages:
            messages = self._convert_messages(agent_request.messages)

        agent_state: AgentState = AgentState(
            authenticated_user=authenticated_user,
            messages=messages,
            normalized_query="",
            resolved_query="",
            intent=QueryIntent.otro.value,
            entities={},
            keywords=[],
            retrieved_fragments=[],
            reranked_fragments=[],
            context="",
            answer="",
            guardrail_passed=False,
            fallback_triggered=False,
        )

        logger.debug("Agent state built", extra={"message_count": len(messages)})
        return agent_state

    @staticmethod
    def _convert_messages(messages: Optional[list[Message]]) -> List[BaseMessage]:
        converted: List[BaseMessage] = []

        for index, message in enumerate(messages):
            try:
                if message.role == MessageRole.human:
                    converted.append(HumanMessage(content=message.content))
                elif message.role == MessageRole.assistant:
                    converted.append(AIMessage(content=message.content))
                else:
                    logger.warning(
                        "Unknown message role — skipping",
                        extra={"index": index, "role": message.role}
                    )
            except Exception as e:
                logger.error(
                    "Error converting message — skipping",
                    extra={"index": index, "error": str(e)},
                    exc_info=True
                )

        logger.debug("Messages converted", extra={"count": len(converted)})
        return converted
