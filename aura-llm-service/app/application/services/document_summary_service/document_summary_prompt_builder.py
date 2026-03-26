import logging
from typing import List, Optional, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class DocumentSummaryPromptBuilder:
    def build_summarization_messages(
            self,
            system_prompt: str,
            fragments: Optional[Sequence[str]],
    ) -> List[BaseMessage]:
        if not fragments:
            logger.debug("No fragments provided — using empty context message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXT]: No relevant information was found in the document to generate a summary."
                )
            ]

        fragments_joined = "\n\n---\n\n".join(
            f"Context fragment {idx + 1}:\n{fragment}"
            for idx, fragment in enumerate(fragments)
        )

        prompt = (
            "Analyze the following document content and generate a complete, structured, and clear summary "
            "that captures the main points and the most important information.\n\n"
            f"Document content:\n\n{fragments_joined}\n\n"
            "Summary:"
        )

        logger.debug(
            "Summarization messages built",
            extra={"fragment_count": len(fragments)}
        )

        return [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

    def build_reduction_messages(
            self,
            system_prompt: str,
            partial_summaries: Optional[Sequence[str]],
    ) -> List[BaseMessage]:
        if not partial_summaries:
            logger.debug("No partial summaries provided — using empty reduction message")
            return [
                self._build_system_message(system_prompt),
                HumanMessage(
                    content="[CONTEXT]: No partial summaries were received to reduce/combine."
                )
            ]

        joined_summaries = "\n\n---\n\n".join(
            f"Partial summary {idx + 1}:\n{summary}"
            for idx, summary in enumerate(partial_summaries)
        )

        prompt = (
            "Below are multiple partial summaries of a larger document. "
            "Merge all of them into a single final summary that is coherent, concise, and free of repetition. "
            "Preserve the structure and main points of each section.\n\n"
            f"Partial summaries:\n\n{joined_summaries}\n\n"
            "Final summary:"
        )

        logger.debug(
            "Reduction messages built",
            extra={"partial_summary_count": len(partial_summaries)}
        )

        return [
            self._build_system_message(system_prompt),
            HumanMessage(content=prompt)
        ]

    @staticmethod
    def _build_system_message(system_prompt: str) -> SystemMessage:
        return SystemMessage(content=system_prompt)
