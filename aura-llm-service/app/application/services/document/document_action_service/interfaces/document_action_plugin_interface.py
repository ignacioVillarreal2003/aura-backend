from abc import ABC, abstractmethod

from app.application.services.document.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)


class DocumentActionPlugin(ABC):
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        pass

    @abstractmethod
    def should_run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> bool:
        pass

    @abstractmethod
    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        pass
