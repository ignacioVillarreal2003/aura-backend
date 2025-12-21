import logging
from typing import Optional, Type
from pydantic import BaseModel, PrivateAttr
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun

from app.application.services.fragment_retrieval_service import FragmentRetrievalService

logger = logging.getLogger(__name__)


class DocumentSummaryToolInput(BaseModel):
    documentId: int


class DocumentSummaryTool(BaseTool):
    name: str = "document_summary_tool"
    description: str = (
        "Generates a comprehensive summary of a document by its ID. "
        "Use this tool when the user asks for a summary, overview, or wants to understand "
        "the main points of a document. The tool retrieves all document fragments and "
        "creates a structured summary."
    )
    args_schema: Type[BaseModel] = DocumentSummaryToolInput

    _fragment_retrieval_service: FragmentRetrievalService = PrivateAttr()

    def __init__(self,
                 fragment_retrieval_service: FragmentRetrievalService,
                 **kwargs):
        super().__init__(**kwargs)
        self._fragment_retrieval_service = fragment_retrieval_service
        logger.debug("DocumentSummaryTool initialized")

    def _run(self,
             document_id: int,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("DocumentSummaryTool does not support synchronous execution.")

    async def _arun(self,
                    document_id: int,
                    run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        logger.debug(f"Executing asynchronous DocumentSummaryTool")

        try:
            fragments = await self._fragment_retrieval_service.get_fragments_by_document_id(
                document_id=document_id
            )

            # todo lo del resumen

            return ""

        except Exception as e:
            logger.error(f"Error executing DocumentSummaryTool: {e}")
            return "An error occurred while generating the document summary."
