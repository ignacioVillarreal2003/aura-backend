import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document.bulk_dispatch_service.bulk_dispatch_service import BulkDispatchService
from app.application.services.document.bulk_dispatch_service.exceptions.bulk_dispatch_service_exception import (
    BulkOperationConflictException,
    BulkOperationUnavailableException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.document_selector import DocumentSelector


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.com", roles=[], permissions=[])


def _db_manager(documents=None):
    session = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    db = MagicMock()
    db.session = MagicMock(return_value=cm)
    return db


def _store(existing_snapshot=None):
    store = AsyncMock()
    store.get_snapshot = AsyncMock(return_value=existing_snapshot)
    store.is_stopped = AsyncMock(return_value=False)
    return store


def _make_service(*, store, db=None, repo=None, reembed=None, graph=None):
    return BulkDispatchService(
        database_manager=db or _db_manager(),
        document_repository=repo or MagicMock(),
        progress_store=store,
        reembed_publisher=reembed,
        graph_extraction_publisher=graph,
    )


async def _drain(service: BulkDispatchService):
    if service._tasks:
        await asyncio.gather(*list(service._tasks))


class TestBulkDispatchService:
    async def test_explicit_ids_enqueue_one_command_each_with_batch_id(self):
        store = _store()
        reembed = AsyncMock()
        service = _make_service(store=store, reembed=reembed)

        result = await service.start(
            operation=BulkOperation.reembed,
            selector=DocumentSelector(document_ids=[10, 11, 12]),
            user=_user(),
        )
        await _drain(service)

        assert result.total == 3
        assert result.queued is True
        store.begin_job.assert_awaited_once()
        assert reembed.publish.await_count == 3
        for call in reembed.publish.await_args_list:
            assert call.kwargs["batch_id"] == result.job_id

    async def test_all_documents_resolves_via_repository(self):
        store = _store()
        repo = MagicMock()
        repo.get_documents = AsyncMock(return_value=[MagicMock(id=1), MagicMock(id=2)])
        reembed = AsyncMock()
        service = _make_service(store=store, repo=repo, reembed=reembed)

        result = await service.start(
            operation=BulkOperation.reembed,
            selector=DocumentSelector(all_documents=True),
            user=_user(),
        )
        await _drain(service)

        assert result.total == 2
        repo.get_documents.assert_awaited_once()
        assert reembed.publish.await_count == 2

    async def test_conflict_when_job_already_running(self):
        store = _store(existing_snapshot={"job_id": "x", "is_running": True})
        service = _make_service(store=store, reembed=AsyncMock())

        with pytest.raises(BulkOperationConflictException):
            await service.start(
                operation=BulkOperation.reembed,
                selector=DocumentSelector(document_ids=[1]),
                user=_user(),
            )

    async def test_unavailable_operation_raises(self):
        store = _store()
        service = _make_service(store=store, reembed=AsyncMock())

        with pytest.raises(BulkOperationUnavailableException):
            await service.start(
                operation=BulkOperation.graph_extract,
                selector=DocumentSelector(document_ids=[1]),
                user=_user(),
            )

    async def test_stop_requests_stop_on_store(self):
        store = _store(existing_snapshot={"job_id": "x", "is_running": True, "total": 5,
                                          "processed": 1, "failed": 0, "errors": []})
        service = _make_service(store=store, reembed=AsyncMock())

        await service.stop(operation=BulkOperation.reembed)
        store.request_stop.assert_awaited_once_with(operation=BulkOperation.reembed)
