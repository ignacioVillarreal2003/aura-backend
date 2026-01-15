import logging
from typing import Optional

from app.application.exceptions.app_exceptions import ValidationError, AppError
from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.application.services.agent_service.agent_node_configuration import AgentNodeConfiguration
from app.application.services.agent_service.sentiment_configuration import SentimentConfiguration
from app.application.services.agent_service.agent_request_validator import AgentRequestValidator
from app.application.services.agent_service.state_builder import StateBuilder
from app.application.services.agent_service.response_extractor import ResponseExtractor
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.agent_response import AgentResponse
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class AgentService:
    """
    Servicio principal para ejecutar workflows de agente con IA.

    Flujo:
    1. Valida el request
    2. Construye el estado inicial
    3. Ejecuta el workflow (sentiment -> agent -> tools -> respuesta)
    4. Extrae y retorna la respuesta

    El workflow soporta:
    - Análisis de sentimiento opcional
    - Uso de tools (RAG, resúmenes, etc.)
    - Límite de iteraciones de tools
    - Manejo de errores robusto

    Thread-safe: El workflow se construye una vez y se reutiliza (inmutable).
    """

    def __init__(
            self,
            llm_facade: OllamaLLMFacadeInterface,
            config: Optional[AgentConfiguration] = None,
            sentiment_config: Optional[SentimentConfiguration] = None,
            agent_config: Optional[AgentNodeConfiguration] = None
    ) -> None:
        """
        Inicializa el servicio del agente.

        Args:
            llm_facade: Fachada del LLM con tools configurados
            config: Configuración general del agente
            sentiment_config: Configuración del análisis de sentimiento
            agent_config: Configuración del comportamiento del agente
        """
        self._llm_facade = llm_facade
        self._config = config or AgentConfiguration()
        self._sentiment_config = sentiment_config
        self._agent_config = agent_config

        # Componentes auxiliares
        self._validator = AgentRequestValidator()

        # Workflow (inicializado lazy)
        self._workflow = None
        self._workflow_initialization_failed = False

        logger.info(
            "AgentService initialized",
            extra={
                "max_tool_iterations": self._config.max_tool_iterations,
                "sentiment_enabled": self._config.enable_sentiment_analysis,
                "default_sentiment": self._config.default_sentiment.value,
                "tools_count": len(llm_facade.tools) if llm_facade.tools else 0
            }
        )

    @classmethod
    def create(
            cls,
            llm_facade: OllamaLLMFacadeInterface,
            max_tool_iterations: Optional[int] = None,
            enable_sentiment_analysis: Optional[bool] = None,
            custom_base_prompt: Optional[str] = None,
            custom_sentiment_prompt: Optional[str] = None
    ) -> "AgentService":
        """
        Factory method para crear el servicio con parámetros individuales.

        Args:
            llm_facade: Fachada del LLM
            max_tool_iterations: Máximo de iteraciones de tools
            enable_sentiment_analysis: Habilitar análisis de sentimiento
            custom_base_prompt: Prompt base personalizado del agente
            custom_sentiment_prompt: Prompt personalizado para sentimiento

        Returns:
            Instancia configurada del servicio
        """
        # Construir configuración general
        config_kwargs = {}
        if max_tool_iterations is not None:
            config_kwargs['max_tool_iterations'] = max_tool_iterations
        if enable_sentiment_analysis is not None:
            config_kwargs['enable_sentiment_analysis'] = enable_sentiment_analysis

        config = AgentConfiguration(**config_kwargs) if config_kwargs else None

        # Construir configuración de agente
        agent_config = None
        if custom_base_prompt is not None:
            agent_config = AgentNodeConfiguration(base_system_prompt=custom_base_prompt)

        # Construir configuración de sentimiento
        sentiment_config = None
        if custom_sentiment_prompt is not None:
            sentiment_config = SentimentConfiguration(system_prompt=custom_sentiment_prompt)

        return cls(
            llm_facade=llm_facade,
            config=config,
            sentiment_config=sentiment_config,
            agent_config=agent_config
        )

    async def execute_agent(self, request: AgentRequest) -> AgentResponse:
        """
        Ejecuta el workflow del agente con el request dado.

        Args:
            request: Request con mensaje del usuario e historial opcional

        Returns:
            Respuesta del agente con answer y tool usado (si aplica)

        Raises:
            ValidationError: Si el request es inválido
            AppError: Si ocurre un error durante la ejecución
        """
        logger.info(
            "Executing agent request",
            extra={
                "message_length": len(request.message),
                "has_history": request.messages is not None,
                "history_count": len(request.messages) if request.messages else 0
            }
        )

        # 1. Validar request
        self._validator.validate_request(request)

        try:
            # 2. Asegurar que el workflow está listo
            await self._ensure_workflow_initialized()

            # 3. Construir estado inicial
            initial_state = StateBuilder.build_initial_state(
                request=request,
                default_sentiment=self._config.default_sentiment
            )

            # 4. Ejecutar workflow
            logger.debug("Invoking workflow")
            final_state = await self._workflow.ainvoke(initial_state)

            # 5. Extraer respuesta
            response = ResponseExtractor.extract_response(final_state)

            logger.info(
                "Agent request executed successfully",
                extra={
                    "answer_length": len(response.answer),
                    "tool_used": response.tool_used
                }
            )

            return response

        except ValidationError:
            # Re-lanzar errores de validación sin modificar
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during agent execution",
                extra={"error_type": type(e).__name__}
            )
            raise AppError(
                message=f"Error inesperado al ejecutar el agente: {str(e)}",
                status_code=500,
                code="AgentServiceError"
            ) from e

    async def _ensure_workflow_initialized(self) -> None:
        """
        Asegura que el workflow esté construido y listo (lazy loading).

        Raises:
            AppError: Si la inicialización falla
        """
        # Si ya está inicializado, retornar
        if self._workflow is not None:
            return

        # Si ya intentamos y falló, no reintentar
        if self._workflow_initialization_failed:
            raise AppError(
                message="El workflow del agente no pudo ser inicializado previamente",
                status_code=500,
                code="WorkflowInitializationFailed"
            )

        logger.debug("Building workflow for first time (lazy loading)")

        try:
            # Construir workflow
            builder = AgentWorkflowBuilder(
                llm_facade=self._llm_facade,
                config=self._config,
                sentiment_config=self._sentiment_config,
                agent_config=self._agent_config
            )

            self._workflow = await builder.build()

            logger.info("Workflow initialized successfully")

        except Exception as e:
            self._workflow_initialization_failed = True
            logger.error(
                "Failed to initialize workflow",
                extra={"error_type": type(e).__name__},
                exc_info=True
            )
            raise AppError(
                message="Error al inicializar el workflow del agente",
                status_code=500,
                code="WorkflowInitializationError"
            ) from e
