import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.application.services.document.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document.document_summary_service.steps.generate_summary_direct.generate_summary_direct_prompt import (
    DIRECT_SUMMARY_HUMAN_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class GenerateSummaryDirectPlugin(DocumentSummaryPlugin):
    @property
    def plugin_name(self) -> str:
        return "generate_summary_direct"

    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        return state.strategy == SummarizationStrategy.direct and bool(state.fragments)

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        logger.debug(
            "Executing direct summarization",
            extra={"fragment_count": len(state.fragments)},
        )

        fragments_joined = "\n\n---\n\n".join(
            f"Fragmento de contexto {idx + 1}:\n{fragment.content}"
            for idx, fragment in enumerate(state.fragments)
        )

        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=DIRECT_SUMMARY_HUMAN_PROMPT.format(fragments_joined=fragments_joined)
            ),
        ]

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            raw = await resources.llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Direct summarization LLM call failed")
            raise DocumentSummaryServiceException(
                "Error generating the document summary"
            ) from e

        summary = raw.strip() if raw else ""
        if not summary:
            logger.warning("LLM returned empty summary in direct mode")
            raise DocumentSummaryServiceException("The model did not generate a valid summary")

        state.summary = summary
        logger.debug("Direct summarization completed successfully")
