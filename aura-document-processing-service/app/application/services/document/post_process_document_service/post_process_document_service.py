import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface,
)
from app.application.services.document.post_process_document_service.post_process_document_service_settings import (
    PostProcessDocumentServiceSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.http.llm_provider.llm_provider_settings import LlmProviderSettings
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


def _safe_fragment_index(fragment: Fragment) -> int:
    try:
        return int(fragment.fragment_index)
    except (TypeError, ValueError):
        return 0


class PostProcessDocumentService(PostProcessDocumentServiceInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            llm_provider_settings: Optional[LlmProviderSettings] = None,
            post_process_document_service_settings: Optional[PostProcessDocumentServiceSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._llm_settings = llm_provider_settings or LlmProviderSettings()
        self._settings = post_process_document_service_settings or PostProcessDocumentServiceSettings()

    async def process_document_metadata(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ValueError(f"Document {document_id} was not found.")

            fragments = await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session,
            )
            document_name = document.name
            content = self._build_classification_content(document, fragments)

        classification = await self._llm_provider.classify_document(
            document_name=document_name,
            content=content,
            authenticated_user=user,
        )

        async def _operation(session: AsyncSession) -> None:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ValueError(f"Document {document_id} was not found.")

            document.type = (
                classification.type.value
                if hasattr(classification.type, "value")
                else classification.type
            )
            document.category = classification.category
            document.description = classification.description

            await self._document_repository.update_document(
                document=document,
                database_session=session,
            )

        await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="post_process_document.update_document_metadata",
        )

        logger.info(
            "Document metadata was updated after classification.",
            extra={"document_id": document_id},
        )

    def _build_classification_content(
            self,
            document: Document,
            fragments: list[Fragment],
    ) -> str:
        max_len = self._llm_settings.max_classify_content_length
        sample = self._select_sample_fragments(fragments)
        parts: list[str] = []
        total = 0
        for fragment in sample:
            piece = (fragment.content or "").strip()
            if not piece:
                continue
            if total + len(piece) + 1 > max_len:
                remaining = max_len - total - 1
                if remaining > 0:
                    parts.append(piece[:remaining])
                break
            parts.append(piece)
            total += len(piece) + 1
        body = "\n".join(parts).strip()
        if not body:
            return document.name
        return body

    def _select_sample_fragments(
            self,
            fragments: list[Fragment],
    ) -> list[Fragment]:
        ordered = sorted(fragments, key=lambda f: _safe_fragment_index(f))
        sample_size = self._settings.classify_sample_size
        total = len(ordered)
        if total <= sample_size:
            return ordered

        last = total - 1
        picked_indices = sorted(
            {round(i * last / (sample_size - 1)) for i in range(sample_size)}
        )
        return [ordered[index] for index in picked_indices]
