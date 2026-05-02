import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.application.services.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class ContextRetrieverNode(RagNodeInterface):
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("ContextRetrieverNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing context retriever")

        query: str = state.get("query", "")
        keywords: List[str] = state.get("keywords", [])
        authenticated_user: AuthenticatedUser = state["authenticated_user"]

        if not query:
            logger.warning("No query available for retrieval")
            return {"retrieved_fragments": [], "context": ""}

        try:
            fragments = await self._retrieve(authenticated_user, query, keywords)
            context = self._build_context(fragments)
            logger.info(
                "Context retrieved",
                extra={"fragments_count": len(fragments), "context_chars": len(context)},
            )
            return {"retrieved_fragments": fragments, "context": context}
        except Exception:
            logger.error("Context retrieval failed — returning empty context", exc_info=True)
            return {"retrieved_fragments": [], "context": ""}

    async def _retrieve(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        keywords_str = self._build_keywords_string(keywords)
        use_keywords = bool(keywords_str)

        response = await self._provider.retrieve_context_fragments_by_question(
            authenticated_user=authenticated_user,
            question=query,
            question_max_fragments=self._settings.max_fragments,
            use_keywords=use_keywords if use_keywords else None,
            keywords=keywords_str if use_keywords else None,
            keywords_max_fragments=self._settings.max_fragments if use_keywords else None,
            use_rerank=None,
            rerank_max_fragments=None,
        )
        return response.fragments

    def _build_context(self, fragments: List[FragmentResponse]) -> str:
        if not fragments:
            return ""

        grouped: Dict[int, List[FragmentResponse]] = defaultdict(list)
        for fragment in fragments:
            grouped[fragment.document_id].append(fragment)

        for doc_id in grouped:
            grouped[doc_id].sort(key=lambda f: f.fragment_index)

        parts: List[str] = []
        total_chars = 0

        for doc_id, doc_fragments in grouped.items():
            section_parts = [f"=== Documento #{doc_id} ==="]
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

    @staticmethod
    def _build_keywords_string(keywords: List[str]) -> Optional[str]:
        if not keywords:
            return None
        joined = " ".join(keywords)
        return joined[:16_000] if joined else None
