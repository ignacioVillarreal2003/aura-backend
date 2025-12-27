import logging
from typing import Optional, Type, List
from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun
)

from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class DocumentQuestionToolInput(BaseModel):
    question: str = Field(...)


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

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentQuestionTool does not support synchronous execution")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug(
            "Executing DocumentQuestionTool",
            extra={
                "question": question
            }
        )

        try:
            fragments: List[str] = await self._context_provider.retrieve_fragments_by_question(
                question=question,
                max_fragments=self._max_fragments
            )

            if not fragments:
                logger.info("No fragments found for query")
                return "No relevant information was found for the given question."

            formatted_fragments = "\n".join(f"- {fragment}" for fragment in fragments)

            result = (
                f"[CONTEXT]\n"
                f"Question: {question}\n\n"
                f"Relevant fragments:\n{formatted_fragments}"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error executing DocumentQuestionTool: {e}",
                exc_info=True
            )
            return "An error occurred while retrieving contextual information."
