import logging
from collections import defaultdict
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.application.services.generation_shared.processors.processor_observability import (
    attached_documents_dropped_total,
    attached_fetch_total,
    attached_fragments_selected,
    log_extra,
    timed,
)
from app.configuration.tracing import generation_span
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)

_STAGE = "attached_documents"


class AttachedDocumentsProcessor:
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            attached_documents_settings: Optional[AttachedDocumentsSettings] = None,
    ) -> None:
        self._settings = attached_documents_settings or AttachedDocumentsSettings()
        self._document_context_provider = document_context_provider

    async def run(self, state: GenerationState) -> None:
        document_ids = self._unique_document_ids(state.document_ids)
        if not document_ids:
            state.attached_fragments = []
            return

        with timed(_STAGE), generation_span(_STAGE):
            fetched = await self._fetch(state, document_ids)
            if fetched is None:
                attached_fetch_total.labels(outcome="failure").inc()
                state.attached_degraded = True
                state.attached_fragments = []
                return

            selected = self._select_fragments(fetched, document_ids)
            state.attached_fragments = selected
            attached_fragments_selected.observe(len(selected))
            attached_fetch_total.labels(outcome="success" if selected else "empty").inc()
            self._log_outcome(state, document_ids, fetched, selected)

    async def _fetch(
            self,
            state: GenerationState,
            document_ids: list[int],
    ) -> Optional[list[FragmentResponse]]:
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_document(
                authenticated_user=state.authenticated_user,
                document_ids=document_ids,
            )
        except Exception:
            logger.warning(
                "Attached document retrieval failed; continuing without attachments. "
                "Answer quality may degrade: explicitly attached documents are missing.",
                extra=log_extra(user_id=state.authenticated_user.id, document_count=len(document_ids)),
                exc_info=True,
            )
            return None

        fragments = getattr(result, "fragments", None)
        if not isinstance(fragments, list):
            logger.warning(
                "Attached document retrieval returned an unexpected payload; treating as empty.",
                extra=log_extra(user_id=state.authenticated_user.id),
            )
            return []
        return fragments

    def _select_fragments(
            self,
            fragments: list[FragmentResponse],
            requested_ids: list[int],
    ) -> list[FragmentResponse]:
        if not fragments:
            return []
        ordered = (
            self._round_robin_by_document(fragments, requested_ids)
            if self._settings.fair_distribution
            else fragments
        )
        return self._apply_budget(ordered)

    def _round_robin_by_document(
            self,
            fragments: list[FragmentResponse],
            requested_ids: list[int],
    ) -> list[FragmentResponse]:
        by_document: dict[int, list[FragmentResponse]] = defaultdict(list)
        for fragment in fragments:
            by_document[fragment.document_id].append(fragment)
        for bucket in by_document.values():
            bucket.sort(key=lambda f: f.fragment_index)

        requested_set = set(requested_ids)
        visit_order = [doc_id for doc_id in requested_ids if doc_id in by_document]
        visit_order += [doc_id for doc_id in by_document if doc_id not in requested_set]

        interleaved: list[FragmentResponse] = []
        depth = 0
        while True:
            added = False
            for doc_id in visit_order:
                bucket = by_document[doc_id]
                if depth < len(bucket):
                    interleaved.append(bucket[depth])
                    added = True
            if not added:
                break
            depth += 1
        return interleaved

    def _apply_budget(self, fragments: list[FragmentResponse]) -> list[FragmentResponse]:
        max_count = self._settings.max_fragments
        max_chars = self._settings.max_chars

        selected: list[FragmentResponse] = []
        used_chars = 0
        for fragment in fragments:
            if len(selected) >= max_count:
                break
            if max_chars is not None:
                fragment_chars = len(fragment.content or "")
                if selected and used_chars + fragment_chars > max_chars:
                    break
                used_chars += fragment_chars
            selected.append(fragment)
        return selected

    @staticmethod
    def _unique_document_ids(document_ids: Optional[list[int]]) -> list[int]:
        seen: set[int] = set()
        unique: list[int] = []
        for document_id in document_ids or []:
            if document_id not in seen:
                seen.add(document_id)
                unique.append(document_id)
        return unique

    def _log_outcome(
            self,
            state: GenerationState,
            requested_ids: list[int],
            fetched: list[FragmentResponse],
            selected: list[FragmentResponse],
    ) -> None:
        covered = {fragment.document_id for fragment in selected}
        missing = [doc_id for doc_id in requested_ids if doc_id not in covered]

        logger.debug(
            "Attached document fragments selected.",
            extra=log_extra(
                user_id=state.authenticated_user.id,
                requested_documents=len(requested_ids),
                documents_covered=len(covered),
                fetched_fragments=len(fetched),
                selected_fragments=len(selected),
            ),
        )
        if missing:
            attached_documents_dropped_total.inc(len(missing))
            logger.warning(
                "Some attached documents contributed no fragments after budgeting; "
                "consider raising ATTACHED_DOCUMENTS_MAX_FRAGMENTS.",
                extra=log_extra(user_id=state.authenticated_user.id, missing_document_ids=missing),
            )
