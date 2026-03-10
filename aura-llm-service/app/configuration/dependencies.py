import logging
from asyncio import Lock

from app.application.services.agent_service.interfaces.agent_service_interface import AgentServiceInterface
from app.application.services.agent_service.tools.document_question_tool.document_question_tool import (
    DocumentQuestionTool
)
from app.application.services.agent_service.tools.document_summary_tool.document_summary_tool import (
    DocumentSummaryTool
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.ollama_llm_facade_factory import (
    get_global_ollama_llm_facade_base,
    get_global_ollama_llm_facade_with_tools,
    shutdown_global_ollama_llm_facades
)
from app.infrastructure.ollama_llm.ollama_tool_manager import ToolFactory
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
from app.infrastructure.http_client.http_client_factory import get_global_http_client, shutdown_global_http_client
from app.configuration.environment_variables import environment_variables
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_document_question_service: DocumentQuestionServiceInterface | None = None
_document_question_service_lock = Lock()

_document_summary_service: DocumentSummaryServiceInterface | None = None
_document_summary_service_lock = Lock()


async def get_http_client() -> HttpClientInterface:
    return await get_global_http_client()


async def get_document_context_provider() -> DocumentContextProviderInterface:
    http_client = await get_http_client()
    return DocumentContextProvider.create(
        http_client=http_client,
        question_context_fragments_url=environment_variables.question_context_fragments_url,
        document_context_fragments_url=environment_variables.document_context_fragments_url
    )


async def get_ollama_llm_facade_base() -> OllamaLLMFacadeInterface:
    return await get_global_ollama_llm_facade_base(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url
    )


async def get_document_question_service() -> DocumentQuestionServiceInterface:
    global _document_question_service

    async with _document_question_service_lock:
        if _document_question_service is None:
            ollama_llm_facade = await get_ollama_llm_facade_base()
            document_context_provider = await get_document_context_provider()
            _document_question_service = DocumentQuestionService.create(
                ollama_llm_facade=ollama_llm_facade,
                document_context_provider=document_context_provider
            )
        return _document_question_service


async def get_document_summary_service() -> DocumentSummaryServiceInterface:
    global _document_summary_service

    async with _document_summary_service_lock:
        if _document_summary_service is None:
            ollama_llm_facade = await get_ollama_llm_facade_base()
            document_context_provider = await get_document_context_provider()
            _document_summary_service = DocumentSummaryService.create(
                ollama_llm_facade=ollama_llm_facade,
                document_context_provider=document_context_provider
            )
        return _document_summary_service


async def initialize_tools() -> None:
    await get_document_question_service()
    await get_document_summary_service()


def create_document_question_tool_factory() -> ToolFactory:
    def factory() -> DocumentQuestionTool:
        global _document_question_service
        if _document_question_service is None:
            raise RuntimeError("DocumentQuestionService not initialized. Call initialize_tools() first.")
        return DocumentQuestionTool(
            document_question_service=_document_question_service
        )

    return factory


def create_document_summary_tool_factory() -> ToolFactory:
    def factory() -> DocumentSummaryTool:
        global _document_summary_service
        if _document_summary_service is None:
            raise RuntimeError("DocumentSummaryService not initialized. Call initialize_tools() first.")
        return DocumentSummaryTool(
            document_summary_service=_document_summary_service
        )

    return factory


async def get_agent_service() -> AgentServiceInterface:
    ollama_llm_facade = await get_global_ollama_llm_facade_with_tools(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url,
        tool_factories=[
            create_document_question_tool_factory(),
            create_document_summary_tool_factory(),
        ]
    )
    return AgentService.create(
        ollama_llm_facade=ollama_llm_facade
    )


async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        http_client = await get_http_client()
        if not http_client.is_started:
            await http_client.start()

        await get_ollama_llm_facade_base()
        await initialize_tools()
        await get_agent_service()

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Failed to start dependencies")
        raise


async def shutdown_dependencies() -> None:
    global _document_question_service, _document_summary_service

    try:
        logger.info("Shutting down application dependencies")

        await shutdown_global_http_client()
        await shutdown_global_ollama_llm_facades()

        _document_question_service = None
        _document_summary_service = None

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")