from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document.reembed_document_service.reembed_document_service import (
    ReembedDocumentService,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


def _user(user_id: int = 3) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _frag(fragment_id, *, content="c", embedding_identity="old",
          contextualized_content=None, contextualized_embedding_identity=None):
    return SimpleNamespace(
        id=fragment_id,
        content=content,
        embedding_identity=embedding_identity,
        contextualized_content=contextualized_content,
        contextualized_embedding_identity=contextualized_embedding_identity,
    )


class _FakeDatabaseManager:
    def __init__(self) -> None:
        self.session_obj = MagicMock(name="session")

    @asynccontextmanager
    async def session(self):
        yield self.session_obj

    async def run_write_transaction_with_retry(self, operation, operation_name=""):
        await operation(self.session_obj)


def _make_service(fragments):
    embedder_factory = MagicMock()
    embedder_factory.get_active_model_name.return_value = "model"
    embedder_factory.get_vector_dimension.return_value = 1024
    embedder_factory.get_active_embedding_identity.return_value = "new"
    embedder_factory.embedder.aembed_documents = AsyncMock(
        side_effect=lambda texts: [[0.0] * 3 for _ in texts]
    )

    document_repository = AsyncMock()
    document_repository.get_document_by_id.return_value = SimpleNamespace(id=1)

    fragment_repository = AsyncMock()
    fragment_repository.get_fragments_for_reembedding.return_value = fragments

    service = ReembedDocumentService(
        document_repository=document_repository,
        fragment_repository=fragment_repository,
        embedder_factory=embedder_factory,
        database_manager=_FakeDatabaseManager(),
    )
    return service, fragment_repository


class TestReembedDualRepresentation:
    async def test_refreshes_both_when_stale(self):
        fragments = [
            _frag(1, embedding_identity="old",
                  contextualized_content="ctx", contextualized_embedding_identity="old"),
        ]
        service, repo = _make_service(fragments)

        count = await service.reembed_document(document_id=1, user=_user())

        assert count == 2
        repo.update_fragment_embedding.assert_awaited_once()
        repo.update_fragment_contextualized_embedding.assert_awaited_once()

    async def test_refreshes_contextual_only_when_raw_current(self):
        fragments = [
            _frag(1, embedding_identity="new",
                  contextualized_content="ctx", contextualized_embedding_identity="old"),
        ]
        service, repo = _make_service(fragments)

        count = await service.reembed_document(document_id=1, user=_user())

        assert count == 1
        repo.update_fragment_embedding.assert_not_awaited()
        repo.update_fragment_contextualized_embedding.assert_awaited_once()

    async def test_skips_fragment_without_contextual_content(self):
        fragments = [_frag(1, embedding_identity="new", contextualized_content=None)]
        service, repo = _make_service(fragments)

        count = await service.reembed_document(document_id=1, user=_user())

        assert count == 0
        repo.update_fragment_embedding.assert_not_awaited()
        repo.update_fragment_contextualized_embedding.assert_not_awaited()
