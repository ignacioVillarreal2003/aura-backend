import logging
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class AttachedDocumentsProcessor:
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            attached_documents_settings: Optional[AttachedDocumentsSettings] = None,
    ) -> None:
        self._settings = attached_documents_settings or AttachedDocumentsSettings()
        self._document_context_provider = document_context_provider

    async def run(self, state: GenerationState) -> None:
        if not state.document_ids:
            return
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_document(
                authenticated_user=state.authenticated_user,
                document_ids=state.document_ids,
            )
            state.attached_fragments = result.fragments[:self._settings.max_attached_fragments]
            logger.debug(
                "Attached document fragments retrieved",
                extra={
                    "fragment_count": len(state.attached_fragments),
                    "document_count": len(state.document_ids),
                },
            )
        except Exception:
            logger.warning(
                "Attached document retrieval failed; continuing without attachments",
                extra={"user_id": state.authenticated_user.id},
                exc_info=True,
            )
            state.attached_fragments = []
