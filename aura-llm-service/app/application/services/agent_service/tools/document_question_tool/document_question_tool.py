import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.agent_service.tools.document_question_tool.document_question_tool_input import (
    DocumentQuestionToolInput
)
from app.application.services.document_question_service.document_question_service import DocumentQuestionService
from app.infrastructure.document_context_provider.interfaces.document_context_provider_interface import (
    ContextProviderInterface
)
from app.infrastructure.llm_facade.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class DocumentQuestionTool(BaseTool):
    name: str = "document_question_tool"
    description: str = (
        "Retrieves relevant information from document knowledge base and answers questions. "
        "Use this when you need to access specific information from uploaded documents or "
        "when answering questions that require domain-specific knowledge. "
        "Returns both the relevant context and a generated answer."
    )
    args_schema: Type[BaseModel] = DocumentQuestionToolInput

    _document_question_service: DocumentQuestionService = PrivateAttr()

    def __init__(self,
                 context_provider: ContextProviderInterface,
                 ollama_llm_facade: OllamaLLMFacadeInterface,
                 **kwargs):
        super().__init__(**kwargs)

        self._document_question_service = DocumentQuestionService(
            context_provider=context_provider,
            ollama_llm_facade=ollama_llm_facade
        )

        logger.info("DocumentQuestionTool initialized")

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentQuestionTool only supports async execution via _arun")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.info(
            "DocumentQuestionTool invoked by agent",
            extra={
                "question": question
            }
        )

        try:
            fragments = await self._document_question_service.retrieve_fragments_by_question(
                question=question
            )

            if not fragments:
                logger.info("No relevant fragments found")
                return self._format_no_results_response(question)

            answer = await self._document_question_service.answer_question(
                question=question,
                fragments=fragments
            )

            result = self._format_success_response(
                question=question,
                fragments=fragments,
                answer=answer
            )

            logger.info(
                "DocumentQuestionTool executed successfully",
                extra={
                    "question": question,
                    "fragments": fragments,
                    "answer": answer
                }
            )

            return result

        except Exception as e:
            logger.error(
                "Error executing DocumentQuestionTool",
                extra={
                    "question": question,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return self._format_error_response(question, str(e))

    @staticmethod
    def _format_success_response(question: str,
                                 fragments: list[str],
                                 answer: str) -> str:
        fragments_formatted = "\n".join(
            f"  [{i + 1}] {fragment[:200]}..." if len(fragment) > 200 else f"  [{i + 1}] {fragment}"
            for i, fragment in enumerate(fragments)
        )

        return (
            f"📄 DOCUMENT CONTEXT RETRIEVED\n\n"
            f"Question: {question}\n\n"
            f"Relevant Fragments ({len(fragments)}):\n{fragments_formatted}\n\n"
            f"Generated Answer:\n{answer}"
        )

    @staticmethod
    def _format_no_results_response(question: str) -> str:
        return (
            f"📄 DOCUMENT CONTEXT SEARCH\n\n"
            f"Question: {question}\n\n"
            f"Result: No relevant information found in the document knowledge base. "
            f"Unable to provide a context-based answer."
        )

    @staticmethod
    def _format_error_response(question: str,
                               error: str) -> str:
        return (
            f"❌ DOCUMENT CONTEXT ERROR\n\n"
            f"Question: {question}\n\n"
            f"Error: An error occurred while retrieving document context: {error}"
        )
