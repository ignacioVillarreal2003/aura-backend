import logging
from typing import List, Optional, Dict, Any

from app.application.agent_workflow.agent_workflow import create_agent_workflow
from app.application.exceptions.app_exceptions import AppError
from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self,
                 llm_configurator: LLMConfiguratorInterface) -> None:
        self._llm_configurator = llm_configurator
        self._workflow = create_agent_workflow(self._llm_configurator)
        
        logger.info("AgentService initialized")

    async def execute_agent(self,
                            request: AgentRequest) -> AgentResponse:
        logger.info(
            "Executing agent request",
            extra={
                "message_length": len(request.message)
            }
        )

        try:
            initial_state = self._build_initial_state(request)
            
            final_state = await self._workflow.ainvoke(initial_state)
            
            response = self._extract_response(final_state)
            
            logger.info("Agent request executed successfully")
            
            return response

        except Exception as e:
            logger.exception("Unexpected error during agent execution")
            raise AppError(
                message=f"Error inesperado al ejecutar el agente: {str(e)}",
                status_code=500,
                code="AgentServiceError"
            ) from e

    def _build_initial_state(self, request: AgentRequest) -> Dict[str, Any]:
        messages = []
        if request.messages:
             messages = self._convert_history_messages(request.messages)
        
        # Add current message
        from langchain_core.messages import HumanMessage
        messages.append(HumanMessage(content=request.message))
        
        return {
            "messages": messages,
            "sentiment": "NEUTRAL" # Default, will be updated by sentiment node
        }

    def _convert_history_messages(self, messages: List[Message]) -> List[Any]:
        from langchain_core.messages import HumanMessage, AIMessage
        
        history = []
        for msg in messages:
            if msg.role == "user":
                history.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history.append(AIMessage(content=msg.content))
        return history

    def _extract_response(self, state: Dict[str, Any]) -> AgentResponse:
        messages = state.get("messages", [])
        if not messages:
             return AgentResponse(answer="No se generó ninguna respuesta.")
             
        last_message = messages[-1]
        answer = last_message.content if hasattr(last_message, "content") else str(last_message)
        
        # We could extract tool usage if needed from history
        tool_used = None
        
        return AgentResponse(
            answer=answer,
            tool_used=tool_used
        )
