import logging
from functools import lru_cache

from app.application.services.agent_service.agent_workflow.agent_workflow import create_agent_workflow
from app.application.llm_facade.interfaces.llm_facade_interface import LLMFacadeInterface
from app.application.llm_facade.ollama_llm_facade import get_global_ollama_llm_facade
from app.application.services.document_question_service.document_question_service import DocumentQuestionService
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.application.services.document_summary_service.document_summary_service import DocumentSummaryService
from app.application.services.agent_service.agent_service import AgentService
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import \
    DocumentSummaryServiceInterface
from app.application.services.agent_service.tools.document_question_tool import DocumentQuestionTool
from app.application.services.agent_service.tools.document_summary_tool import DocumentSummaryTool
from app.infrastructure.http_client.http_client import get_global_http_client
from app.configuration.environment_variables import environment_variables
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.providers.context_provider import ContextProvider
from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
async def get_http_client() -> HttpClientInterface:
    return await get_global_http_client()


async def get_context_provider() -> ContextProviderInterface:
    http_client = await get_http_client()
    return ContextProvider(
        http_client=http_client,
        retrieve_fragments_by_question_url=environment_variables.retrieve_fragments_by_question_url,
        retrieve_fragments_by_document_url=environment_variables.retrieve_fragments_by_document_url
    )


@lru_cache(maxsize=1)
async def get_llm_facade() -> LLMFacadeInterface:
    tools_factories = [get_document_question_tool, get_document_summary_tool]
    return await get_global_ollama_llm_facade(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url,
        tool_factories=tools_factories
    )


async def get_document_question_service() -> DocumentQuestionServiceInterface:
    llm_facade = await get_llm_facade()
    context_provider = await get_context_provider()
    return DocumentQuestionService.with_defaults(
        llm_facade=llm_facade,
        context_provider=context_provider
    )


async def get_document_summary_service() -> DocumentSummaryServiceInterface:
    llm_facade = await get_llm_facade()
    context_provider = await get_context_provider()
    return DocumentSummaryService.with_defaults(
        llm_facade=llm_facade,
        context_provider=context_provider
    )


















def get_document_question_tool() -> DocumentQuestionTool:
    context_provider = get_context_provider()
    return DocumentQuestionTool(
        context_provider=context_provider,
        max_fragments=3
    )


def get_document_summary_tool() -> DocumentSummaryTool:
    document_summary_service = get_document_summary_service()
    return DocumentSummaryTool(
        document_summary_service=document_summary_service,
    )


@lru_cache(maxsize=1)
def get_agent_workflow():
    llm_configurator = get_llm_configurator()
    return create_agent_workflow(
        llm_configurator=llm_configurator
    )


def get_agent_service() -> AgentService:
    llm_configurator = get_llm_configurator()
    return AgentService(
        llm_configurator=llm_configurator
    )


async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        http_client = get_http_client()
        http_client.start()

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Failed to start dependencies")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down application dependencies")

        http_client = get_http_client()
        await http_client.stop()

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
