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
from app.domain.field_limits import MAX_POST_PROCESS_ERROR_MESSAGE_CHARS
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
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


def _safe_fragment_index(fragment) -> int:
    try:
        return int(fragment.fragment_index)
    except (TypeError, ValueError):
        return 0


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

        document_ids_raw = manifest.get("document_ids")
        if document_ids_raw is not None:
            document_ids: list[int] = list(document_ids_raw)
            if not document_ids:
                await self._job_progress_store.complete_document_job(job_id)
                return
            await self._run_explicit_documents(job_id=job_id, document_ids=document_ids, user=user)
        else:
            await self._run_all_documents(job_id=job_id, user=user)

    async def _run_explicit_documents(
            self,
            *,
            job_id: str,
            document_ids: list[int],
            user: AuthenticatedUser,
    ) -> None:
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
                    raw = str(e) or type(e).__name__
                    msg = f"{type(e).__name__}: {raw}"[:2000]
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

    async def _run_all_documents(
            self,
            *,
            job_id: str,
            user: AuthenticatedUser,
    ) -> None:
        _page = 100
        failed_ids: set[int] = set()
        try:
            while True:
                if await self._job_progress_store.is_document_stop_requested(job_id):
                    logger.info(
                        "Document post-processing stopped cooperatively.",
                        extra={"job_id": job_id},
                    )
                    break

                async with self._database_manager.session() as session:
                    batch = await self._document_repository.get_documents_missing_metadata(
                        database_session=session,
                        limit=_page + len(failed_ids),
                        offset=0,
                    )

                pending = [d for d in batch if d.id not in failed_ids]
                if not pending:
                    break

                stop_outer = False
                for doc in pending:
                    if await self._job_progress_store.is_document_stop_requested(job_id):
                        stop_outer = True
                        break

                    await self._job_progress_store.mark_document_job_progress(
                        job_id,
                        current_document_id=doc.id,
                    )

                    try:
                        await self._process_single_document(
                            job_id=job_id,
                            document_id=doc.id,
                            user=user,
                        )
                        await self._job_progress_store.mark_document_job_progress(
                            job_id,
                            processed_increment=1,
                        )
                    except Exception as e:
                        failed_ids.add(doc.id)
                        raw = str(e) or type(e).__name__
                        msg = f"{type(e).__name__}: {raw}"[:MAX_POST_PROCESS_ERROR_MESSAGE_CHARS]
                        await self._job_progress_store.append_document_job_error(
                            job_id,
                            PostProcessDocumentError(
                                document_id=doc.id,
                                error=msg,
                            ).model_dump(mode="json"),
                        )
                        await self._job_progress_store.mark_document_job_progress(
                            job_id,
                            failed_increment=1,
                        )
                        logger.exception(
                            "A document failed during post-processing.",
                            extra={"job_id": job_id, "document_id": doc.id},
                        )

                if stop_outer:
                    break
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

        async def _operation(session):
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
        for fragment in sorted(fragments, key=lambda f: _safe_fragment_index(f)):
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
