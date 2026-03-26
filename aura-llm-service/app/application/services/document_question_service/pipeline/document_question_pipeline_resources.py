from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface
)
from app.infrastructure.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface


class DocumentQuestionPipelineResources:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface
    ) -> None:
        self.ollama_llm_facade = ollama_llm_facade
        self.llm_invoker = llm_invoker
        self.document_context_provider = document_context_provider
