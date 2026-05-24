import logging
from collections import defaultdict
from typing import Any, Dict, List

from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse

logger = logging.getLogger(__name__)


class ContextBuilderNode(NodeInterface):
    def __init__(self, settings: AgentServiceSettings) -> None:
        self._settings = settings
        logger.debug("ContextBuilderNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing context builder")

        fragments: List[FragmentResponse] = agent_state.get("retrieved_fragments", [])
        if not fragments:
            logger.info("No fragments available — context will be empty")
            return {"context": ""}

        context = self._build_context(fragments)
        logger.info(
            "Context built",
            extra={"fragments_used": len(fragments), "context_chars": len(context)},
        )
        return {"context": context}

    def _build_context(self, fragments: List[FragmentResponse]) -> str:
        grouped: Dict[int, List[FragmentResponse]] = defaultdict(list)
        for fragment in fragments:
            grouped[fragment.document_id].append(fragment)

        # Sort fragments within each document by their position
        for doc_id in grouped:
            grouped[doc_id].sort(key=lambda f: f.fragment_index)

        parts: List[str] = []
        total_chars = 0

        for doc_id, doc_fragments in grouped.items():
            section_parts: List[str] = [f"=== Documento #{doc_id} ==="]
            section_chars = len(section_parts[0])

            for i, fragment in enumerate(doc_fragments, start=1):
                remaining = self._settings.max_context_chars - total_chars - section_chars
                if remaining <= 0:
                    break

                content = fragment.content[:remaining]
                fragment_text = f"\n[Fragmento {i}]\n{content}"
                section_parts.append(fragment_text)
                section_chars += len(fragment_text)

            section = "\n".join(section_parts)
            total_chars += len(section)
            parts.append(section)

            if total_chars >= self._settings.max_context_chars:
                break

        return "\n\n".join(parts)
