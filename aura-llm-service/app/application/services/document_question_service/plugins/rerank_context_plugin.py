from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage

from app.application.services.document_question_service.prompts.context_selection_prompt import (
    CONTEXT_SELECTION_PROMPT,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)

logger = logging.getLogger(__name__)


class RerankContextPlugin(DocumentQuestionPlugin):
    @property
    def plugin_name(self) -> str:
        return "rerank_context"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return len(state.retrieved_fragments) > resources.settings.rerank_threshold

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        logger.debug(
            "Running context selection",
            extra={
                "total_fragments": len(state.retrieved_fragments),
                "max_reranked": resources.settings.max_reranked_fragments,
            },
        )

        try:
            query = state.effective_query or state.current_message.content
            numbered_chunks = "\n\n".join(
                f"[{i}] {fragment}" for i, fragment in enumerate(state.retrieved_fragments)
            )
            content = CONTEXT_SELECTION_PROMPT.format(
                query=query,
                chunks=numbered_chunks,
                max_fragments=resources.settings.max_reranked_fragments,
            )
            prompt = [HumanMessage(content=content)]

            llm = await resources.ollama_llm_facade.get_llm_base()
            raw_response = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=prompt,
            )

            selected = self._parse_selection_indices(
                raw=raw_response,
                max_index=len(state.retrieved_fragments) - 1,
            )

            if not selected:
                logger.warning(
                    "Context selection returned no valid indices, keeping all fragments",
                )
                return

            logger.debug(
                "Context selection complete",
                extra={"selected_indices": selected},
            )
            state.retrieved_fragments = [state.retrieved_fragments[i] for i in selected]
        except Exception:
            logger.warning(
                "Context selection failed, keeping all retrieved fragments",
                exc_info=True,
            )

    @staticmethod
    def _parse_selection_indices(raw: str, max_index: int) -> list[int]:
        if not raw:
            return []

        start = raw.find("[")
        end = raw.rfind("]")

        if start == -1 or end == -1 or end <= start:
            logger.warning(
                "No JSON array found in context selection response",
                extra={"raw": raw},
            )
            return []

        try:
            indices = json.loads(raw[start: end + 1])
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse JSON from context selection response",
                extra={"raw": raw},
            )
            return []

        if not isinstance(indices, list):
            return []

        valid = [
            int(i)
            for i in indices
            if isinstance(i, (int, float)) and 0 <= int(i) <= max_index
        ]

        return list(dict.fromkeys(valid))
