import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class RagAgentStateBuilder:
    def build(
            self,
            agent_request: AgentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> RagAgentState:
        messages: List[BaseMessage] = self._convert_messages(agent_request.messages)

        return RagAgentState(
            authenticated_user=authenticated_user,
            messages=messages,
            chat_id=agent_request.chat_id,
            operator_system_prompt=agent_request.system_prompt,
            response_style=agent_request.response_style,
            query="",
            keywords=[],
            intent="",
            retrieved_fragments=[],
            context="",
            graph_facts="",
            answer="",
            guardrail_passed=True,
            fallback_triggered=False,
            retrieval_attempts=0,
            context_sufficient=True,
            grade_reason="",
            can_retry=False,
        )

    @staticmethod
    def _convert_messages(messages: Optional[list[Message]]) -> List[BaseMessage]:
        if not messages:
            return []

        converted: List[BaseMessage] = []
        for index, message in enumerate(messages):
            try:
                if message.role == MessageRole.human:
                    converted.append(HumanMessage(content=message.content))
                elif message.role == MessageRole.assistant:
                    converted.append(AIMessage(content=message.content))
                else:
                    logger.warning("Unknown message role — skipping", extra={"index": index, "role": message.role})
            except Exception as e:
                logger.error("Error converting message — skipping", extra={"index": index, "error": str(e)})

        return converted
