import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.fragment_retrieval_service import FragmentRetrievalService

logger = logging.getLogger(__name__)


class DocumentQuestionToolInput(BaseModel):
    question: str


class DocumentQuestionTool(BaseTool):
    name: str = "document_question_tool"
    description: str = (
        "Retrieves relevant information fragments related to the user's question "
        "from an external knowledge base. Use this to get context before answering."
    )
    args_schema: Type[BaseModel] = DocumentQuestionToolInput

    _fragment_retrieval_service: FragmentRetrievalService = PrivateAttr()
    _max_fragments: int = PrivateAttr(default=3)

    def __init__(self,
                 fragment_retrieval_service: FragmentRetrievalService,
                 max_fragments: int = 3,
                 **kwargs):
        super().__init__(**kwargs)
        self._fragment_retrieval_service = fragment_retrieval_service
        self._max_fragments = max_fragments
        logger.debug("DocumentQuestionTool initialized")

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentQuestionTool does not support synchronous execution")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug("Executing asynchronous DocumentQuestionTool")

        try:
            fragments = await self._fragment_retrieval_service.get_fragments(
                question=question,
                max_fragments=self._max_fragments
            )

            if not fragments:
                logger.info("No fragments found")
                return "No relevant information was found for the given query."

            formatted_fragments = "\n".join(f"- {fragment}" for fragment in fragments)

            result = (
                f"[CONTEXT]\n"
                f"Query: {question}\n\n"
                f"Relevant fragments:\n{formatted_fragments}"
            )

            return result

        except Exception as e:
            logger.error(f"Error executing DocumentQuestionTool: {e}")
            return "An error occurred while retrieving contextual information."
