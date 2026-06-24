"""Unit tests for the DI startup registry and its rollback semantics.

Critical path: if any startup step fails, already-started resources must be
cleaned up in reverse order and removed from app.state, and a failing cleanup
step must not abort the remaining rollback.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from app.configuration.dependency_registry import DependencyRegistry


def _app() -> FastAPI:
    return FastAPI()


def test_register_sets_state_attribute():
    app = _app()
    registry = DependencyRegistry(app)

    registry.register("foo", "instance-foo")

    assert app.state.foo == "instance-foo"


@pytest.mark.asyncio
async def test_rollback_runs_cleanups_in_reverse_order():
    app = _app()
    registry = DependencyRegistry(app)
    order: list[str] = []

    registry.register("first", object(), cleanup=AsyncMock(side_effect=lambda: order.append("first")))
    registry.register("second", object(), cleanup=AsyncMock(side_effect=lambda: order.append("second")))

    await registry.rollback()

    assert order == ["second", "first"]


@pytest.mark.asyncio
async def test_rollback_removes_state_attributes():
    app = _app()
    registry = DependencyRegistry(app)
    registry.register("with_cleanup", object(), cleanup=AsyncMock())
    registry.register("without_cleanup", object())

    await registry.rollback()

    assert not hasattr(app.state, "with_cleanup")
    assert not hasattr(app.state, "without_cleanup")


@pytest.mark.asyncio
async def test_rollback_continues_after_a_failing_cleanup():
    app = _app()
    registry = DependencyRegistry(app)

    failing = AsyncMock(side_effect=RuntimeError("dispose failed"))
    survivor = AsyncMock()
    registry.register("survivor", object(), cleanup=survivor)
    registry.register("failing", object(), cleanup=failing)

    await registry.rollback()

    failing.assert_awaited_once()
    survivor.assert_awaited_once()
    assert not hasattr(app.state, "survivor")
    assert not hasattr(app.state, "failing")


@pytest.mark.asyncio
async def test_commit_prevents_rollback_from_cleaning_up():
    app = _app()
    registry = DependencyRegistry(app)
    cleanup = AsyncMock()
    registry.register("committed", object(), cleanup=cleanup)

    registry.commit()
    await registry.rollback()

    cleanup.assert_not_awaited()
    assert hasattr(app.state, "committed")
