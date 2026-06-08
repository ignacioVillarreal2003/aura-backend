import logging

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class AttachedDocumentsProcessor:
    def __init__(
            self,
            settings: GenerationSettings,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = settings
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
