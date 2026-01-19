import logging

from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.application.services.agent_service.tools.document_question_tool.document_question_tool import (
    DocumentQuestionTool
)
from app.application.services.agent_service.tools.document_summary_tool.document_summary_tool import (
    DocumentSummaryTool
)
from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm_facade.ollama_llm_facade import OllamaLLMFacade
from app.application.services.agent_service.agent_service import AgentService
from app.application.services.document_question_service.document_question_service import DocumentQuestionService
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.application.services.document_summary_service.document_summary_service import DocumentSummaryService
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.infrastructure.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.http_client.http_client_factory import get_global_http_client
from app.configuration.environment_variables import environment_variables
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

# =============================================================================
# HTTP Client
# =============================================================================
_http_client: HttpClientInterface | None = None


async def get_http_client() -> HttpClientInterface:
    global _http_client
    if _http_client is None:
        _http_client = await get_global_http_client()
    return _http_client


# =============================================================================
# Document Context Provider
# =============================================================================
async def get_document_context_provider() -> DocumentContextProviderInterface:
    http_client = await get_http_client()
    return DocumentContextProvider.create(
        http_client=http_client,
        retrieve_context_fragments_by_question_url=environment_variables.retrieve_context_fragments_by_question_url,
        retrieve_context_fragments_by_document_url=environment_variables.retrieve_context_fragments_by_document_url
    )


# =============================================================================
# Ollama LLM Facade (Two-Phase Initialization to avoid recursion)
# =============================================================================
_ollama_llm_facade_base: OllamaLLMFacadeInterface | None = None  # Sin tools, para services
_ollama_llm_facade: OllamaLLMFacadeInterface | None = None       # Con tools, para el agente

# Services cacheados para las tools
_document_question_service: DocumentQuestionServiceInterface | None = None
_document_summary_service: DocumentSummaryServiceInterface | None = None


async def _get_ollama_llm_facade_base() -> OllamaLLMFacadeInterface:
    """
    Facade SIN tools, usado internamente por los services.
    Esto evita la recursión: services necesitan facade, pero facade con tools necesita services.
    """
    global _ollama_llm_facade_base
    if _ollama_llm_facade_base is None:
        _ollama_llm_facade_base = OllamaLLMFacade.create(
            ollama_model_name=environment_variables.ollama_model_name,
            ollama_base_url=environment_variables.ollama_base_url,
            tool_factories=[]  # Sin tools
        )
        await _ollama_llm_facade_base.initialize()
    return _ollama_llm_facade_base


async def _initialize_services_for_tools() -> None:
    """
    Inicializa los services que las tools necesitan.
    Usa el facade base (sin tools) para evitar recursión.
    """
    global _document_question_service, _document_summary_service

    if _document_question_service is not None and _document_summary_service is not None:
        return

    facade_base = await _get_ollama_llm_facade_base()
    document_context_provider = await get_document_context_provider()

    if _document_question_service is None:
        _document_question_service = DocumentQuestionService.create(
            ollama_llm_facade=facade_base,
            document_context_provider=document_context_provider
        )

    if _document_summary_service is None:
        _document_summary_service = DocumentSummaryService.create(
            ollama_llm_facade=facade_base,
            document_context_provider=document_context_provider
        )


def _create_document_question_tool() -> DocumentQuestionTool:
    """Factory síncrona para DocumentQuestionTool (requerida por OllamaToolManager)."""
    if _document_question_service is None:
        raise RuntimeError("DocumentQuestionService not initialized. Call _initialize_services_for_tools() first.")
    return DocumentQuestionTool(document_question_service=_document_question_service)


def _create_document_summary_tool() -> DocumentSummaryTool:
    """Factory síncrona para DocumentSummaryTool (requerida por OllamaToolManager)."""
    if _document_summary_service is None:
        raise RuntimeError("DocumentSummaryService not initialized. Call _initialize_services_for_tools() first.")
    return DocumentSummaryTool(document_summary_service=_document_summary_service)


async def get_ollama_llm_facade() -> OllamaLLMFacadeInterface:
    """
    Facade CON tools, para uso del agente.
    Primero inicializa los services, luego crea el facade con las factories.
    """
    global _ollama_llm_facade
    if _ollama_llm_facade is None:
        # Fase 1: Inicializar services (usa facade base sin tools, sin recursión)
        await _initialize_services_for_tools()

        # Fase 2: Crear facade con tools
        _ollama_llm_facade = OllamaLLMFacade.create(
            ollama_model_name=environment_variables.ollama_model_name,
            ollama_base_url=environment_variables.ollama_base_url,
            tool_factories=[
                _create_document_question_tool,
                _create_document_summary_tool,
            ]
        )
        await _ollama_llm_facade.initialize()
    return _ollama_llm_facade


# =============================================================================
# Document Services (para uso externo, usan el facade base)
# =============================================================================
async def get_document_question_service() -> DocumentQuestionServiceInterface:
    """Retorna el service de document question. Usa facade base (sin tools)."""
    await _initialize_services_for_tools()
    return _document_question_service


async def get_document_summary_service() -> DocumentSummaryServiceInterface:
    """Retorna el service de document summary. Usa facade base (sin tools)."""
    await _initialize_services_for_tools()
    return _document_summary_service


# =============================================================================
# Agent Service
# =============================================================================
async def get_agent_service() -> AgentServiceInterface:
    ollama_llm_facade = await get_ollama_llm_facade()
    return AgentService.create(
        ollama_llm_facade=ollama_llm_facade
    )


# =============================================================================
# Application Lifecycle
# =============================================================================
async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        http_client = await get_http_client()
        await http_client.start()

        # El facade ya se inicializa en get_ollama_llm_facade()
        await get_ollama_llm_facade()

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Failed to start dependencies")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down application dependencies")

        if _http_client is not None:
            await _http_client.stop()

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
