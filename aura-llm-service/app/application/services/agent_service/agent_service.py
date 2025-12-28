import logging
from typing import List, Dict, Any

from app.application.services.agent_service.agent_workflow.agent_workflow import create_agent_workflow
from app.application.exceptions.app_exceptions import AppError
from app.application.llm_configurator.interfaces.llm_configurator_interface import LLMConfiguratorInterface
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentService:
    """
    Service for executing agent workflows.

    Orchestrates sentiment analysis, tool usage, and response generation.
    """

    def __init__(
            self,
            llm_configurator: LLMConfiguratorInterface,
            config: Optional[AgentConfig] = None
    ):
        """
        Initialize agent service.

        Args:
            llm_configurator: LLM configurator with tools
            config: Optional agent configuration
        """
        self._llm_configurator = llm_configurator
        self._config = config or AgentConfig()

        # Validator
        self._validator = AgentRequestValidator()

        # Workflow (initialized lazily)
        self._workflow = None

        logger.info(
            "AgentService initialized",
            extra={
                "max_tool_iterations": self._config.max_tool_iterations,
                "sentiment_enabled": self._config.enable_sentiment_analysis
            }
        )

    async def execute_agent(
            self,
            request: AgentRequest
    ) -> AgentResponse:
        """
        Execute agent workflow with request.

        Args:
            request: Agent request with message and history

        Returns:
            Agent response with answer

        Raises:
            ValidationError: If request is invalid
            AppError: If execution fails
        """
        # Validate request
        self._validator.validate_request(request)

        logger.info(
            "Executing agent request",
            extra={"message_length": len(request.message)}
        )

        try:
            # Ensure workflow is initialized
            await self._ensure_workflow_initialized()

            # Build initial state
            initial_state = StateBuilder.build_initial_state(
                request=request,
                default_sentiment=self._config.default_sentiment
            )

            # Execute workflow
            final_state = await self._workflow.ainvoke(initial_state)

            # Extract response
            response = ResponseExtractor.extract_response(final_state)

            logger.info("Agent request executed successfully")

            return response

        except ValidationError:
            # Re-raise validation errors
            raise

        except Exception as e:
            logger.exception("Unexpected error during agent execution")
            raise AppError(
                message=f"Error inesperado al ejecutar el agente: {str(e)}",
                status_code=500,
                code="AgentServiceError"
            ) from e

    async def _ensure_workflow_initialized(self) -> None:
        """Ensure workflow is built and ready."""
        if self._workflow is None:
            logger.debug("Building workflow for first time")

            builder = AgentWorkflowBuilder(
                llm_configurator=self._llm_configurator,
                config=self._config
            )

            self._workflow = await builder.build()

    @property
    def config(self) -> AgentConfig:
        """Get service configuration (read-only)."""
        return self._config