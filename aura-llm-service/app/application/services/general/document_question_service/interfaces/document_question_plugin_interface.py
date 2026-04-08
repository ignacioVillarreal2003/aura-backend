from abc import ABC, abstractmethod

from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState
)


class DocumentQuestionPlugin(ABC):
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        pass

    @abstractmethod
    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources
    ) -> bool:
        pass

    @abstractmethod
    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources
    ) -> None:
        pass
