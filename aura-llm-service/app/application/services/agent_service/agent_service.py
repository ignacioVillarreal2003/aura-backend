import logging
from typing import Optional, Tuple

from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.application.services.agent_service.agent_node.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.agent_workflow import AgentWorkflow
from app.application.services.agent_service.constants.sentimient import Sentiment
from app.application.services.agent_service.exceptions.agent_service_exceptions import AgentServiceError
from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.application.services.agent_service.sentiment_node.sentiment_node_configuration import (
    SentimentNodeConfiguration
)
from app.application.services.agent_service.agent_request_validator import AgentRequestValidator
from app.application.services.agent_service.agent_state.agent_state_builder import AgentStateBuilder
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentService(AgentServiceInterface):
    def __init__(self,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 agent_configuration: Optional[AgentConfiguration] = None,
                 sentiment_node_configuration: Optional[SentimentNodeConfiguration] = None,
                 agent_node_configuration: Optional[AgentNodeConfiguration] = None) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._agent_configuration = agent_configuration or AgentConfiguration()
        self._sentiment_node_configuration = sentiment_node_configuration or SentimentNodeConfiguration()
        self._agent_node_configuration = agent_node_configuration or AgentNodeConfiguration()

        self._agent_request_validator = AgentRequestValidator(
            agent_configuration=agent_configuration
        )

        self._agent_workflow = AgentWorkflow(
            ollama_llm_facade=self._ollama_llm_facade,
            agent_configuration=self._agent_configuration,
            sentiment_node_configuration=self._sentiment_node_configuration,
            agent_node_configuration=self._agent_node_configuration
        )
        self._workflow_built = False

        self._agent_state_builder = AgentStateBuilder()

        logger.info("AgentService initialized")

    @classmethod
    def create(cls,
               ollama_llm_facade: OllamaLLMFacadeInterface,
               message_length: Optional[Tuple[int, int]] = None,
               max_messages_count: Optional[int] = None,
               max_tool_iterations: Optional[int] = None,
               sentiment: Optional[Sentiment] = None,
               sentiment_custom_system_prompt: Optional[str] = None,
               agent_custom_system_prompt: Optional[str] = None,
               custom_sentiment_instructions: Optional[str] = None) -> "AgentService":
        config_kwargs = {}

        if message_length is not None:
            config_kwargs['message_length'] = message_length
        if max_messages_count is not None:
            config_kwargs['max_messages_count'] = max_messages_count
        if max_tool_iterations is not None:
            config_kwargs['max_tool_iterations'] = max_tool_iterations
        if sentiment is not None:
            config_kwargs['sentiment'] = sentiment

        agent_configuration = None
        if config_kwargs is not None:
            agent_configuration = AgentConfiguration(**config_kwargs)

        config_kwargs = {}

        if sentiment_custom_system_prompt is not None:
            config_kwargs['sentiment_custom_system_prompt'] = sentiment_custom_system_prompt

        sentiment_node_configuration = None
        if config_kwargs is not None:
            sentiment_node_configuration = SentimentNodeConfiguration(**config_kwargs)

        config_kwargs = {}

        if agent_custom_system_prompt is not None:
            config_kwargs['custom_system_prompt'] = agent_custom_system_prompt
        if custom_sentiment_instructions is not None:
            config_kwargs['custom_sentiment_instructions'] = custom_sentiment_instructions

        agent_node_configuration = None
        if config_kwargs is not None:
            agent_node_configuration = AgentNodeConfiguration(**config_kwargs)

        return cls(
            ollama_llm_facade=ollama_llm_facade,
            agent_configuration=agent_configuration,
            sentiment_node_configuration=sentiment_node_configuration,
            agent_node_configuration=agent_node_configuration
        )

    async def _ensure_workflow_built(self) -> None:
        if not self._workflow_built:
            await self._agent_workflow.build()
            self._workflow_built = True

    async def execute_agent(self,
                            request: AgentRequest) -> AgentResponse:
        logger.info(
            "Executing agent_node request"
        )

        self._agent_request_validator.validate_request(request)

        try:
            await self._ensure_workflow_built()

            initial_agent_state = self._agent_state_builder.build_agent_state(
                request=request
            )

            final_agent_state = await self._agent_workflow.invoke(initial_agent_state)

            logger.info(
                "Agent request executed successfully"
            )

            processed_messages = []
            for message in final_agent_state.get("messages", []):
                if isinstance(message, str):
                    processed_messages.append(str(message))
                else:
                    processed_messages.append(str(message.content) if hasattr(message, 'content') else str(message))

            return AgentResponse(
                answer=processed_messages[-1] if processed_messages else ""
            )

        except Exception as e:
            logger.exception(
                "Unexpected error during agent_node execution",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise AgentServiceError(
                message=f"Error inesperado al ejecutar el agente: {str(e)}",
                status_code=500
            ) from e
