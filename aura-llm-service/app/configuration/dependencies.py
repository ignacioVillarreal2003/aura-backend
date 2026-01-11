import logging

from app.infrastructure.ollama_llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm_facade.ollama_llm_facade_factory import get_global_ollama_llm_facade
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

_http_client: HttpClientInterface | None = None


async def get_http_client() -> HttpClientInterface:
    global _http_client
    if _http_client is None:
        _http_client = await get_global_http_client()
    return _http_client


async def get_document_context_provider() -> DocumentContextProviderInterface:
    http_client = await get_http_client()
    return DocumentContextProvider.with_defaults(
        http_client=http_client,
        retrieve_context_fragments_by_question_url=environment_variables.retrieve_context_fragments_by_question_url,
        retrieve_context_fragments_by_document_url=environment_variables.retrieve_context_fragments_by_document_url
    )


_ollama_llm_facade: OllamaLLMFacadeInterface | None = None


async def get_ollama_llm_facade() -> OllamaLLMFacadeInterface:
    global _ollama_llm_facade
    if _ollama_llm_facade is None:
        tools_factories = []
        _ollama_llm_facade = await get_global_ollama_llm_facade(
            ollama_model_name=environment_variables.ollama_model_name,
            ollama_base_url=environment_variables.ollama_base_url,
            tool_factories=tools_factories
        )
    return _ollama_llm_facade


async def get_document_question_service() -> DocumentQuestionServiceInterface:
    ollama_llm_facade = await get_ollama_llm_facade()
    document_context_provider = await get_document_context_provider()
    return DocumentQuestionService.create(
        ollama_llm_facade=ollama_llm_facade,
        document_context_provider=document_context_provider
    )


async def get_document_summary_service() -> DocumentSummaryServiceInterface:
    ollama_llm_facade = await get_ollama_llm_facade()
    document_context_provider = await get_document_context_provider()
    return DocumentSummaryService.create(
        ollama_llm_facade=ollama_llm_facade,
        document_context_provider=document_context_provider
    )


async def get_agent_service() -> AgentService:
    pass


async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        http_client = await get_http_client()
        await http_client.start()

        ollama_llm_facade = await get_ollama_llm_facade()
        await ollama_llm_facade.initialize()

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Failed to start dependencies")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down application dependencies")

        await _http_client.stop()

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
