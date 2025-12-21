import logging
from functools import lru_cache

from app.application.agent_workflow.agent_workflow import AgentWorkflow, create_agent_workflow
from app.application.services.document_question_service import DocumentQuestionService
from app.application.services.document_summary_service import DocumentSummaryService
from app.application.services.fragment_retrieval_service import FragmentRetrievalService
from app.application.services.agent_service import AgentService
from app.application.tools.document_question_tool import DocumentQuestionTool
from app.application.tools.document_summary_tool import DocumentSummaryTool
from app.infrastructure.http.http_client import HttpClient, get_global_http_client
from app.application.ollama_configurator.ollama_configurator import (
    OllamaConfigurator,
    get_global_ollama_configurator
)
from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


def get_http_client() -> HttpClient:
    return get_global_http_client()


def get_fragment_retrieval_service() -> FragmentRetrievalService:
    http_client = get_http_client()
    base_url = environment_variables.document_processing_service_base_url
    
    # Construir URLs completas
    fragments_url = f"{base_url}{environment_variables.fragment_retrieve_url_get_fragments}"
    fragments_by_id_url = (
        f"{base_url}{environment_variables.fragment_retrieve_url_get_fragments_by_document_id}"
    )
    
    return FragmentRetrievalService(
        http_client=http_client,
        fragment_retrieval_url=fragments_url,
        fragment_retrieval_url_by_document_id=fragments_by_id_url
    )


def get_rag_tool() -> DocumentQuestionTool:
    fragment_retrieval_service = get_fragment_retrieval_service()
    return DocumentQuestionTool(
        fragment_retrieval_service=fragment_retrieval_service,
        max_fragments=3
    )


def get_ollama_configurator_base() -> OllamaConfigurator:
    """Obtiene un OllamaConfigurator sin tools para servicios que no los necesitan."""
    return get_global_ollama_configurator(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url,
        tool_factories=None
    )


def get_summary_tool() -> DocumentSummaryTool:
    fragment_retrieval_service = get_fragment_retrieval_service()
    ollama_configurator = get_ollama_configurator_base()
    return DocumentSummaryTool(
        fragment_retrieval_service=fragment_retrieval_service,
        ollama_configurator=ollama_configurator
    )


@lru_cache(maxsize=1)
def get_ollama_configurator() -> OllamaConfigurator:
    return get_global_ollama_configurator(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url,
        tool_factories=[get_rag_tool, get_summary_tool]
    )


@lru_cache(maxsize=1)
def get_agent_workflow():
    ollama_configurator = get_ollama_configurator()
    config = AgentWorkflow(
        enable_sentiment_analysis=environment_variables.enable_sentiment_analysis,
        max_tool_iterations=environment_variables.max_tool_iterations
    )

    workflow = create_agent_workflow(ollama_configurator, config)

    return workflow


def get_document_question_service() -> DocumentQuestionService:
    http_client = get_http_client()
    ollama_configurator = get_ollama_configurator()
    fragment_retrieval_service = get_fragment_retrieval_service()
    return DocumentQuestionService(
        http_client=http_client,
        ollama_configurator=ollama_configurator,
        fragment_retrieval_service=fragment_retrieval_service,
        max_fragments=3
    )


def get_document_summary_service() -> DocumentSummaryService:
    ollama_configurator = get_ollama_configurator()
    fragment_retrieval_service = get_fragment_retrieval_service()
    return DocumentSummaryService(
        ollama_configurator=ollama_configurator,
        fragment_retrieval_service=fragment_retrieval_service
    )


def get_agent_service() -> AgentService:
    ollama_configurator = get_ollama_configurator()
    return AgentService(
        ollama_configurator=ollama_configurator
    )


async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        http_client = get_http_client()
        http_client.start()

        ollama_configurator = get_ollama_configurator()
        ollama_configurator.initialize()

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
