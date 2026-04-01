from typing import Iterable

from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState
)
from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin
)


class DocumentQuestionPipeline:
    def __init__(self, plugins: Iterable[DocumentQuestionPlugin]) -> None:
        self._plugins = list(plugins)

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        for plugin in self._plugins:
            if plugin.should_run(state=state, resources=resources):
                await plugin.run(state=state, resources=resources)
