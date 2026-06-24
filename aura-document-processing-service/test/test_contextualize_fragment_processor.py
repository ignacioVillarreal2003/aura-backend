from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.fragment.contextualize_fragment_service.contextualize_fragment_processor import (
    ContextualizeFragmentProcessor,
)
from app.application.services.fragment.contextualize_fragment_service.contextualize_fragment_service_settings import (
    ContextualizeFragmentServiceSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.processing_status import ProcessingStatus


def _user(user_id: int = 7) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _fragment(fragment_id: int, content: str):
    return MagicMock(id=fragment_id, content=content)


class _FakeDatabaseManager:
    """Minimal stand-in: session() is an async CM and write transactions run inline."""

    def __init__(self) -> None:
        self.session_obj = MagicMock(name="session")

    @asynccontextmanager
    async def session(self):
        yield self.session_obj

    async def run_write_transaction_with_retry(self, operation, operation_name=""):
        await operation(self.session_obj)


def _make_processor(
        *,
        description="Resumen del documento.",
        name="Documento",
        fragments=None,
        llm_provider=None,
        embedder_factory=None,
        fragment_repository=None,
):
    document = MagicMock(description=description)
    document.name = name

    document_repository = AsyncMock()
    document_repository.get_document_by_id.return_value = document

    fragment_repository = fragment_repository or AsyncMock()
    fragment_repository.get_fragments_by_document_id.return_value = fragments or []

    if embedder_factory is None:
        embedder_factory = MagicMock()
        embedder_factory.embedder.aembed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        embedder_factory.get_active_embedding_identity.return_value = "model:dim:instr"

    if llm_provider is None:
        llm_provider = AsyncMock()
        llm_provider.contextualize_fragment.return_value = MagicMock(context="Contexto situacional.")

    processor = ContextualizeFragmentProcessor(
        database_manager=_FakeDatabaseManager(),
        document_repository=document_repository,
        fragment_repository=fragment_repository,
        llm_provider=llm_provider,
        embedder_factory=embedder_factory,
        contextualize_fragment_service_settings=ContextualizeFragmentServiceSettings(),
    )
    return processor, fragment_repository, llm_provider, embedder_factory


class TestContextualizeDocumentFragments:
    async def test_prepends_context_and_persists(self):
        fragments = [_fragment(1, "Contenido original del fragmento.")]
        processor, repo, llm, embedder = _make_processor(fragments=fragments)

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_awaited_once()
        _, kwargs = llm.contextualize_fragment.call_args
        assert kwargs["document_summary"] == "Resumen del documento."
        assert kwargs["content"] == "Contenido original del fragmento."

        embedder.embedder.aembed_documents.assert_awaited_once()
        embedded_text = embedder.embedder.aembed_documents.call_args.args[0][0]
        assert embedded_text == "Contexto situacional.\n\nContenido original del fragmento."

        repo.update_fragment_contextualization.assert_awaited_once()
        _, kwargs = repo.update_fragment_contextualization.call_args
        assert kwargs["fragment_id"] == 1
        assert kwargs["contextualized_content"].endswith("Contenido original del fragmento.")
        assert kwargs["contextualized_vector"] == [0.1, 0.2, 0.3]
        assert kwargs["contextualized_embedding_identity"] == "model:dim:instr"
        assert kwargs["status"] == ProcessingStatus.processed.value

    async def test_no_description_marks_not_required_and_skips_llm(self):
        fragments = [_fragment(1, "Contenido.")]
        processor, repo, llm, embedder = _make_processor(
            description=None, name="", fragments=fragments
        )

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_not_awaited()
        embedder.embedder.aembed_documents.assert_not_awaited()
        repo.update_fragment_contextualization_status.assert_awaited()
        _, kwargs = repo.update_fragment_contextualization_status.call_args
        assert kwargs["status"] == ProcessingStatus.not_required.value

    async def test_falls_back_to_document_name_when_no_description(self):
        fragments = [_fragment(1, "Contenido.")]
        processor, repo, llm, _ = _make_processor(
            description=None, name="Reglamento X", fragments=fragments
        )

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_awaited_once()
        _, kwargs = llm.contextualize_fragment.call_args
        assert kwargs["document_summary"] == "Reglamento X"

    async def test_llm_failure_marks_fragment_failed(self):
        fragments = [_fragment(1, "Contenido.")]
        llm = AsyncMock()
        llm.contextualize_fragment.side_effect = RuntimeError("LLM down")
        processor, repo, _, _ = _make_processor(fragments=fragments, llm_provider=llm)

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        repo.update_fragment_contextualization.assert_not_awaited()
        repo.update_fragment_contextualization_status.assert_awaited()
        _, kwargs = repo.update_fragment_contextualization_status.call_args
        assert kwargs["status"] == ProcessingStatus.failed.value

    async def test_no_fragments_is_noop(self):
        processor, repo, llm, embedder = _make_processor(fragments=[])

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_not_awaited()
        repo.update_fragment_contextualization.assert_not_awaited()


class TestIncrementalBackfill:
    @staticmethod
    def _done_fragment(fragment_id: int, identity: str = "model:dim:instr"):
        return MagicMock(
            id=fragment_id,
            content="Contenido.",
            contextualized_content="ctx\n\nContenido.",
            contextualized_embedding_identity=identity,
            contextualization_status=ProcessingStatus.processed.value,
        )

    async def test_skips_already_contextualized_on_active_identity(self):
        fragments = [self._done_fragment(1)]
        processor, repo, llm, embedder = _make_processor(fragments=fragments)

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_not_awaited()
        embedder.embedder.aembed_documents.assert_not_awaited()
        repo.update_fragment_contextualization.assert_not_awaited()

    async def test_reprocesses_when_identity_is_stale(self):
        fragments = [self._done_fragment(1, identity="old-model")]
        processor, repo, llm, embedder = _make_processor(fragments=fragments)

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        llm.contextualize_fragment.assert_awaited_once()
        repo.update_fragment_contextualization.assert_awaited_once()

    async def test_processes_only_missing_fragments_in_mixed_doc(self):
        done = self._done_fragment(1)
        pending = _fragment(2, "Nuevo contenido.")
        processor, repo, llm, embedder = _make_processor(fragments=[done, pending])

        await processor.contextualize_document_fragments(document_id=10, user=_user())

        assert llm.contextualize_fragment.await_count == 1
        _, kwargs = repo.update_fragment_contextualization.call_args
        assert kwargs["fragment_id"] == 2
