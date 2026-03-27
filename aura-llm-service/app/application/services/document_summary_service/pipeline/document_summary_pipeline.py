from typing import Iterable

from app.application.services.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)


class DocumentSummaryPipeline:
    def __init__(self, plugins: Iterable[DocumentSummaryPlugin]) -> None:
        self._plugins = list(plugins)

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        for plugin in self._plugins:
            if plugin.should_run(state=state, resources=resources):
                await plugin.run(state=state, resources=resources)
