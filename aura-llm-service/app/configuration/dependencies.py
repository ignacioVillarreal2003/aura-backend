from app.application.services.document_question_service import DocumentQuestionService
from app.application.services.fragment_retrieval_service import FragmentRetrievalService
from app.application.tools.rag_tool import RAGTool
from app.infrastructure.http.http_client import HttpClient
from app.application.ollama_configurator.ollama_configurator import (
    OllamaConfigurator,
    get_global_ollama_configurator
)
from app.configuration.environment_variables import environment_variables


def get_http_client() -> HttpClient:
    return HttpClient()


def get_ollama_configurator() -> OllamaConfigurator:
    return get_global_ollama_configurator(
        ollama_model_name=environment_variables.ollama_model_name,
        ollama_base_url=environment_variables.ollama_base_url,
        tool_factories=[get_rag_tool]
    )


def get_fragment_retrieval_service() -> FragmentRetrievalService:
    http_client = get_http_client()
    return FragmentRetrievalService(
        http_client=http_client,
        fragment_retrieval_url=environment_variables.fragment_retrieve_url
    )


def get_rag_tool() -> RAGTool:
    fragment_retrieval_service = get_fragment_retrieval_service()
    return RAGTool(
        fragment_retrieval_service=fragment_retrieval_service,
        max_fragments=3
    )


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
