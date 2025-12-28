from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage

from app.domain.dtos.agent_response import AgentResponse


class ResponseExtractor:
    @staticmethod
    def extract_response(state: Dict[str, Any]) -> AgentResponse:
        messages = state.get("messages", [])

        if not messages:
            logger.warning("No messages in final state")
            return AgentResponse(
                answer="No se generó ninguna respuesta.",
                tool_used=None
            )

        last_message = messages[-1]

        answer = ResponseExtractor._extract_answer(last_message)

        tool_used = ResponseExtractor._extract_tool_usage(messages)

        return AgentResponse(
            answer=answer,
            tool_used=tool_used
        )

    @staticmethod
    def _extract_answer(message: BaseMessage) -> str:
        if hasattr(message, "content"):
            return str(message.content)
        return str(message)

    @staticmethod
    def _extract_tool_usage(messages: List[BaseMessage]) -> Optional[str]:
        for message in reversed(messages):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                return message.tool_calls[0].get('name')

            if hasattr(message, 'additional_kwargs'):
                tool_calls = message.additional_kwargs.get('tool_calls')
                if tool_calls and len(tool_calls) > 0:
                    return tool_calls[0].get('name')

        return None