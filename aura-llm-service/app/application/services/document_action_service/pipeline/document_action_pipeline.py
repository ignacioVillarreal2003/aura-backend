from typing import Iterable

from app.application.services.document_action_service.interfaces.document_action_plugin_interface import (
    DocumentActionPlugin,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_resources import (
    DocumentActionPipelineResources,
)
from app.application.services.document_action_service.pipeline.document_action_pipeline_state import (
    DocumentActionPipelineState,
)


class DocumentActionPipeline:
    def __init__(self, plugins: Iterable[DocumentActionPlugin]) -> None:
        self._plugins = list(plugins)

    async def run(
            self,
            state: DocumentActionPipelineState,
            resources: DocumentActionPipelineResources,
    ) -> None:
        for plugin in self._plugins:
            if plugin.should_run(state=state, resources=resources):
                await plugin.run(state=state, resources=resources)
