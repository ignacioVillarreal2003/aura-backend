import logging
from fastapi import FastAPI

from app.application.services.agent_service.agent_service import AgentService
from app.application.services.document_question_service.document_question_service import DocumentQuestionService
from app.application.services.document_action_service.document_action_service import DocumentActionService
from app.application.services.document_summary_service.document_summary_service import DocumentSummaryService
from app.infrastructure.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http_client.http_client import HttpClient
from app.infrastructure.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.ollama_llm.ollama_llm_facade import OllamaLLMFacade
from app.infrastructure.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings
from app.infrastructure.ollama_llm.ollama_llm_invoker import OllamaLLMInvoker

logger = logging.getLogger(__name__)


async def startup_dependencies(
        app: FastAPI
) -> None:
    try:
        logger.info("Starting up dependencies")

        http_client = HttpClient()
        await http_client.start()
        app.state.http_client = http_client

        authentication_provider = AuthenticationProvider(http_client=http_client)
        app.state.authentication_provider = authentication_provider

        document_context_provider = DocumentContextProvider(http_client=http_client)
        app.state.document_context_provider = document_context_provider

        ollama_settings = OllamaLLMFacadeSettings()
        ollama_llm_facade_base = OllamaLLMFacade(ollama_llm_facade_settings=ollama_settings)
        await ollama_llm_facade_base.initialize()
        app.state.ollama_llm_facade_base = ollama_llm_facade_base
        ollama_llm_facade_with_tools = OllamaLLMFacade(
            ollama_llm_facade_settings=ollama_settings,
            tool_factories=[]
        )
        await ollama_llm_facade_with_tools.initialize()
        app.state.ollama_llm_facade_with_tools = ollama_llm_facade_with_tools

        llm_invoker = OllamaLLMInvoker()

        agent_service = AgentService(ollama_llm_facade=ollama_llm_facade_with_tools)
        app.state.agent_service = agent_service

        document_question_service = DocumentQuestionService(
            ollama_llm_facade=ollama_llm_facade_base,
            llm_invoker=llm_invoker,
            document_context_provider=document_context_provider
        )
        app.state.document_question_service = document_question_service

        document_summary_service = DocumentSummaryService(
            ollama_llm_facade=ollama_llm_facade_base,
            llm_invoker=llm_invoker,
            document_context_provider=document_context_provider
        )
        app.state.document_summary_service = document_summary_service

        document_action_service = DocumentActionService(
            ollama_llm_facade=ollama_llm_facade_base,
            llm_invoker=llm_invoker,
            document_context_provider=document_context_provider
        )
        app.state.document_action_service = document_action_service

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Error during dependency starting up")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down dependencies")

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
        raise
