
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderError,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_facade_exceptions import OllamaLLMFacadeError
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import OllamaLLMInvokerError

EXPECTED_LLM_ERRORS: tuple[type[Exception], ...] = (
    OllamaLLMInvokerError,
    OllamaLLMFacadeError,
    ValueError,
    TypeError,
    KeyError,
)

EXPECTED_RETRIEVAL_ERRORS: tuple[type[Exception], ...] = (
    DocumentContextProviderError,
)
