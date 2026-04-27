import logging
from typing import Optional

from app.infrastructure.persistence.memory_database.fragment_post_process_job_progress_store.fragment_post_process_job_progress_store_interface import (
    FragmentPostProcessJobProgressStoreInterface,
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_processor_interface import (
    PostProcessFragmentProcessorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment.post_process_fragment.post_process_fragment_error import PostProcessFragmentError
from app.infrastructure.http.llm_provider.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)

_DEFAULT_FRAGMENT_PAGE_SIZE = 50


class PostProcessFragmentProcessor(PostProcessFragmentProcessorInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            job_progress_store: FragmentPostProcessJobProgressStoreInterface,
            fragment_page_size: int = _DEFAULT_FRAGMENT_PAGE_SIZE,
    ) -> None:
        self._database_manager = database_manager
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._job_progress_store = job_progress_store
        self._page_size = max(1, min(fragment_page_size, 500))

    async def run_job(
            self,
            job_id: str,
    ) -> None:
        manifest = await self._job_progress_store.get_fragment_job_manifest(job_id)
        if manifest is None:
            logger.warning(
                "No Redis manifest was found for the fragment post-process job; skipping.",
                extra={"job_id": job_id},
            )
            return

        snapshot = await self._job_progress_store.get_fragment_job_snapshot()
        if snapshot is None or snapshot.get("job_id") != job_id:
            logger.warning(
                "The fragment post-process job snapshot is missing or does not match; skipping.",
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
            await self._job_progress_store.abort_fragment_job(job_id)
            return

        document_ids: Optional[list[int]] = manifest.get("document_ids")
        last_fragment_id: Optional[int] = manifest.get("last_fragment_id")

        try:
            while True:
                if await self._job_progress_store.is_fragment_stop_requested(job_id):
                    logger.info(
                        "Fragment post-processing stopped cooperatively.",
                        extra={"job_id": job_id},
                    )
                    break

                async with self._database_manager.session() as session:
                    if document_ids is None:
                        batch_ids = await self._fragment_repository.get_fragment_ids_missing_metadata(
                            database_session=session,
                            limit=self._page_size,
                            last_fragment_id=last_fragment_id,
                        )
                    else:
                        batch_ids = await self._fragment_repository.get_fragment_ids_missing_metadata_by_document_ids(
                            document_ids=document_ids,
                            database_session=session,
                            limit=self._page_size,
                            last_fragment_id=last_fragment_id,
                        )

                if not batch_ids:
                    break

                stop_outer = False
                for fragment_id in batch_ids:
                    if await self._job_progress_store.is_fragment_stop_requested(job_id):
                        stop_outer = True
                        break

                    await self._job_progress_store.mark_fragment_job_progress(
                        job_id,
                        current_fragment_id=fragment_id,
                    )

                    try:
                        await self._process_single_fragment(
                            job_id=job_id,
                            fragment_id=fragment_id,
                            user=user,
                        )
                        await self._job_progress_store.mark_fragment_job_progress(
                            job_id,
                            processed_increment=1,
                        )
                    except Exception as e:
                        raw = str(e) or type(e).__name__
                        msg = f"{type(e).__name__}: {raw}"[:2000]
                        await self._job_progress_store.append_fragment_job_error(
                            job_id,
                            PostProcessFragmentError(
                                fragment_id=fragment_id,
                                error=msg,
                            ).model_dump(mode="json"),
                        )
                        await self._job_progress_store.mark_fragment_job_progress(
                            job_id,
                            failed_increment=1,
                        )
                        logger.exception(
                            "A fragment failed during post-processing.",
                            extra={"job_id": job_id, "fragment_id": fragment_id},
                        )

                    last_fragment_id = fragment_id
                    await self._job_progress_store.update_fragment_job_cursor(
                        job_id,
                        last_fragment_id=last_fragment_id,
                    )

                if stop_outer:
                    break
        finally:
            await self._job_progress_store.complete_fragment_job(job_id)

    async def _process_single_fragment(
            self,
            *,
            job_id: str,
            fragment_id: int,
            user: AuthenticatedUser,
    ) -> None:
        async with self._database_manager.session() as session:
            fragment = await self._fragment_repository.get_fragment_by_id(
                fragment_id=fragment_id,
                database_session=session,
            )
            if fragment is None:
                raise ValueError(f"Fragment {fragment_id} was not found.")
            fragment_content = fragment.content

        enriched = await self._llm_provider.enrich_fragment(
            content=fragment_content,
            authenticated_user=user,
        )

        async def _operation(session):
            fragment = await self._fragment_repository.get_fragment_by_id(
                fragment_id=fragment_id,
                database_session=session,
            )
            if fragment is None:
                raise ValueError(f"Fragment {fragment_id} was not found.")

            fragment.summary = enriched.summary
            fragment.entities = enriched.entities
            fragment.topics = enriched.topics

            await self._fragment_repository.update_fragment(
                fragment=fragment,
                database_session=session,
            )

        await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="post_process_fragment.update_fragment_metadata",
        )

        logger.info(
            "Fragment metadata was updated after enrichment.",
            extra={"job_id": job_id, "fragment_id": fragment_id},
        )
