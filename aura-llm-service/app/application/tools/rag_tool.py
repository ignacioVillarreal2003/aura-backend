import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.fragment_retrieval_service import FragmentRetrievalService

logger = logging.getLogger(__name__)


class RAGToolInput(BaseModel):
    question: str


class RAGTool(BaseTool):
    name: str = "execute_rag_tool"
    description: str = (
        "Retrieves relevant information fragments related to the user's question "
        "from an external knowledge base. Use this to get context before answering."
    )
    args_schema: Type[BaseModel] = RAGToolInput

    _fragment_retrieval_service: FragmentRetrievalService = PrivateAttr()
    _max_fragments: int = PrivateAttr(default=3)

    def __init__(self,
                 fragment_retrieval_service: FragmentRetrievalService,
                 max_fragments: int = 3,
                 **kwargs):
        super().__init__(**kwargs)
        self._fragment_retrieval_service = fragment_retrieval_service
        self._max_fragments = max_fragments
        logger.debug("RAGTool initialized")

    def _run(self,
             question: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("RAGTool does not support synchronous execution. Use '_arun'.")

    async def _arun(self,
                    question: str,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug("Executing async RAGTool")

        try:
            fragments = await self._fragment_retrieval_service.get_fragments(
                question=question,
                max_fragments=self._max_fragments
            )
        except Exception as e:
            logger.error(f"Error executing RAG retrieval: {e}")
            return "An error occurred while retrieving contextual information from the database."

        if not fragments:
            logger.info("No fragments found")
            return "No relevant information was found for the given query."

        formatted_fragments = "\n".join(f"- {fragment}" for fragment in fragments)

        result = (
            f"[RAG CONTEXT]\n"
            f"Query: {question}\n\n"
            f"Relevant fragments:\n{formatted_fragments}"
        )

        return result
