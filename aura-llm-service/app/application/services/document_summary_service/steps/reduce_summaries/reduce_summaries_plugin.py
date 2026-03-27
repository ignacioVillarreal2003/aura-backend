import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.document_summary_service.interfaces.document_summary_plugin_interface import (
    DocumentSummaryPlugin,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_resources import (
    DocumentSummaryPipelineResources,
)
from app.application.services.document_summary_service.pipeline.document_summary_pipeline_state import (
    DocumentSummaryPipelineState,
)
from app.application.services.document_summary_service.steps.reduce_summaries.reduce_summaries_prompt import (
    REDUCTION_HUMAN_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class ReduceSummariesPlugin(DocumentSummaryPlugin):
    @property
    def plugin_name(self) -> str:
        return "reduce_summaries"

    def should_run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> bool:
        return len(state.partial_summaries) > 0

    async def run(
            self,
            state: DocumentSummaryPipelineState,
            resources: DocumentSummaryPipelineResources,
    ) -> None:
        partial_summaries = state.partial_summaries

        if len(partial_summaries) == 1:
            logger.debug("Single partial summary — skipping LLM reduction step")
            state.summary = partial_summaries[0]
            return

        logger.debug(
            "Reducing partial summaries",
            extra={"partial_summary_count": len(partial_summaries)},
        )

        summaries_joined = "\n\n---\n\n".join(
            f"Resumen parcial {idx + 1}:\n{summary}"
            for idx, summary in enumerate(partial_summaries)
        )

        llm_input = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=REDUCTION_HUMAN_PROMPT.format(summaries_joined=summaries_joined)
            ),
        ]

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            raw = await resources.llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except Exception as e:
            logger.exception("Reduction LLM call failed")
            raise DocumentSummaryServiceException(
                "Error combining partial summaries into the final summary"
            ) from e

        summary = raw.strip() if raw else ""
        if not summary:
            logger.warning("LLM returned empty result during reduction")
            raise DocumentSummaryServiceException("The model did not generate a valid final summary")

        state.summary = summary
        logger.debug("Reduction completed successfully")
