import logging
from typing import Optional, Type, List
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.agent_service.tools.document_question_tool_input import DocumentQuestionToolInput
from app.infrastructure.context_provider.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentQuestionTool(BaseTool):
    name: str = "document_question_tool"
    description: str = (
        "Retrieves relevant information fragments related to the user's question "
        "from an external knowledge base. Use this to get context before answering."
    )
    args_schema: Type[BaseModel] = DocumentQuestionToolInput

    _context_provider: ContextProviderInterface = PrivateAttr()
    _max_fragments: int = PrivateAttr(default=3)

    def __init__(self,
                 context_provider: ContextProviderInterface,
                 max_fragments: int = 3,
                 **kwargs):
        super().__init__(**kwargs)
        self._context_provider = context_provider
        self._max_fragments = max_fragments

        logger.info(
            "DocumentQuestionTool initialized",
            extra={
                "max_fragments": max_fragments
            }
        )

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentQuestionTool does not support synchronous execution")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.info(
            "Executing DocumentQuestionTool",
            extra={
                "question": question,
                "max_fragments": self._max_fragments
            }
        )

        try:
            fragments: List[str] = await self._context_provider.retrieve_fragments_by_question(
                question=question,
                fragments_count=self._max_fragments
            )

            if not fragments:
                logger.info(
                    "No fragments found for query",
                    extra={
                        "question": question
                    }
                )
                return "No relevant information was found for the given question."

            formatted_fragments = "\n".join(f"- {fragment}" for fragment in fragments)

            result = (
                f"[CONTEXT]\n"
                f"Question: {question}\n\n"
                f"Relevant fragments:\n{formatted_fragments}"
            )

            logger.info(
                "DocumentQuestionTool executed successfully",
                extra={
                    "question": question,
                    "fragments_retrieved": len(fragments),
                    "result_length": len(result)
                }
            )

            return result

        except Exception as e:
            logger.error(
                "Error executing DocumentQuestionTool",
                extra={
                    "question": question,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return "An error occurred while retrieving contextual information."
