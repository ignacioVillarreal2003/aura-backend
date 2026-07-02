"""
Tests for shutdown_dependencies resilience:
  - a failing step must not skip the remaining steps (isolation)
  - the reranker warmup task is cancelled/awaited on shutdown
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.configuration.dependencies import shutdown_dependencies


def _app_with(state: dict) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(**state))


class TestShutdownIsolation:
    async def test_failing_step_does_not_skip_later_steps(self):
        rabbitmq_manager = SimpleNamespace(stop=AsyncMock(side_effect=RuntimeError("boom")))
        redis_client = SimpleNamespace(dispose=AsyncMock())
        http_client = SimpleNamespace(stop=AsyncMock())
        minio_manager = SimpleNamespace(stop=AsyncMock())
        db_manager = SimpleNamespace(dispose=AsyncMock())

        app = _app_with(
            {
                "rabbitmq_manager": rabbitmq_manager,
                "redis_client": redis_client,
                "http_client": http_client,
                "minio_manager": minio_manager,
                "db_manager": db_manager,
            }
        )

        await shutdown_dependencies(app)

        rabbitmq_manager.stop.assert_awaited_once()
        redis_client.dispose.assert_awaited_once()
        http_client.stop.assert_awaited_once()
        minio_manager.stop.assert_awaited_once()
        db_manager.dispose.assert_awaited_once()

    async def test_shutdown_tolerates_missing_dependencies(self):
        db_manager = SimpleNamespace(dispose=AsyncMock())
        app = _app_with({"db_manager": db_manager})

        await shutdown_dependencies(app)

        db_manager.dispose.assert_awaited_once()


class TestRerankerWarmupCancellation:
    async def test_pending_warmup_task_is_cancelled(self):
        async def _never_ending():
            await asyncio.Event().wait()

        task = asyncio.create_task(_never_ending())
        await asyncio.sleep(0)  # let the task start

        app = _app_with({"reranker_warmup_task": task})

        await shutdown_dependencies(app)

        assert task.cancelled()

    async def test_completed_warmup_task_is_left_untouched(self):
        async def _done():
            return None

        task = asyncio.create_task(_done())
        await task

        app = _app_with({"reranker_warmup_task": task})

        await shutdown_dependencies(app)

        assert task.done()
        assert not task.cancelled()
