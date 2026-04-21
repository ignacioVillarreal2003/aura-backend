import logging
from typing import Optional

from app.infrastructure.persistence.memory_database.document_post_process_job_progress_store.document_post_process_job_progress_store_interface import (
    DocumentPostProcessJobProgressStoreInterface,
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_processor_interface import (
    PostProcessDocumentProcessorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.post_process_document.post_process_document_error import PostProcessDocumentError
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.http.llm_provider.llm_provider_interface import LlmProviderInterface
from app.infrastructure.http.llm_provider.llm_provider_settings import LlmProviderSettings
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class PostProcessDocumentProcessor(PostProcessDocumentProcessorInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            job_progress_store: DocumentPostProcessJobProgressStoreInterface,
            llm_provider_settings: Optional[LlmProviderSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._job_progress_store = job_progress_store
        self._llm_settings = llm_provider_settings or LlmProviderSettings()

    async def run_job(
            self,
            job_id: str,
    ) -> None:
        manifest = await self._job_progress_store.get_document_job_manifest(job_id)
        if manifest is None:
            logger.warning(
                "No Redis manifest was found for the document post-process job; skipping.",
                extra={"job_id": job_id},
            )
            return

        snapshot = await self._job_progress_store.get_document_job_snapshot()
        if snapshot is None or snapshot.get("job_id") != job_id:
            logger.warning(
                "The document post-process job snapshot is missing or does not match; skipping.",
                extra={"job_id": job_id},
            )
            return

        try:
            user = AuthenticatedUser.model_validate(manifest["user"])
        except Exception as e:
            logger.error(
                "The stored job principal could not be deserialized; aborting the job.",
                extra={"job_id": job_id, "error": type(e).__name__},
            )
            await self._job_progress_store.abort_document_job(job_id)
            return

        document_ids: list[int] = list(manifest.get("document_ids") or [])
        if not document_ids:
            await self._job_progress_store.complete_document_job(job_id)
            return

        try:
            for document_id in document_ids:
                if await self._job_progress_store.is_document_stop_requested(job_id):
                    logger.info(
                        "Document post-processing stopped cooperatively.",
                        extra={"job_id": job_id},
                    )
                    break

                await self._job_progress_store.mark_document_job_progress(
                    job_id,
                    current_document_id=document_id,
                )

                try:
                    await self._process_single_document(
                        job_id=job_id,
                        document_id=document_id,
                        user=user,
                    )
                    await self._job_progress_store.mark_document_job_progress(
                        job_id,
                        processed_increment=1,
                    )
                except Exception as e:
                    msg = (str(e) or type(e).__name__)[:500]
                    await self._job_progress_store.append_document_job_error(
                        job_id,
                        PostProcessDocumentError(
                            document_id=document_id,
                            error=msg,
                        ).model_dump(mode="json"),
                    )
                    await self._job_progress_store.mark_document_job_progress(
                        job_id,
                        failed_increment=1,
                    )
                    logger.exception(
                        "A document failed during post-processing.",
                        extra={"job_id": job_id, "document_id": document_id},
                    )
        finally:
            await self._job_progress_store.complete_document_job(job_id)

    async def _process_single_document(
            self,
            *,
            job_id: str,
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

        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ValueError(f"Document {document_id} was not found.")

            document.type = classification.type
            document.category = classification.category
            document.description = classification.description

            await self._document_repository.update_document(
                document=document,
                database_session=session,
            )
            await session.commit()

        logger.info(
            "Document metadata was updated after classification.",
            extra={"job_id": job_id, "document_id": document_id},
        )

    def _build_classification_content(
            self,
            document: Document,
            fragments: list[Fragment],
    ) -> str:
        max_len = self._llm_settings.max_classify_content_length
        parts: list[str] = []
        total = 0
        for fragment in sorted(fragments, key=lambda f: int(f.fragment_index)):
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
