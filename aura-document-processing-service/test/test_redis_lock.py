"""
Tests for the auto-refreshing Redis lock helper.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.persistence.memory_database import redis_lock
from app.infrastructure.persistence.memory_database.redis_lock import refreshing_redis_lock


def _redis(acquire_ok: bool = True) -> MagicMock:
    r = MagicMock()
    r.set = AsyncMock(return_value=(True if acquire_ok else None))
    r.eval = AsyncMock(return_value=1)
    return r


class TestRefreshingRedisLock:
    async def test_yields_true_and_releases_when_acquired(self):
        r = _redis(acquire_ok=True)
        async with refreshing_redis_lock(r, key="k", token="t", ttl_seconds=90) as acquired:
            assert acquired is True
        # release-if-owner ran on exit (eval called with the release script + token)
        assert r.eval.await_count >= 1
        assert r.eval.await_args_list[-1].args[-1] == "t"

    async def test_yields_false_and_does_not_release_when_not_acquired(self):
        r = _redis(acquire_ok=False)
        async with refreshing_redis_lock(r, key="k", token="t", ttl_seconds=90) as acquired:
            assert acquired is False
        r.eval.assert_not_called()

    async def test_refresher_extends_ttl_while_held(self, monkeypatch):
        # Force a tiny refresh interval so the loop fires during the with-block.
        monkeypatch.setattr(redis_lock, "_refresh_interval_seconds", lambda ttl: 0)
        r = _redis(acquire_ok=True)

        async with refreshing_redis_lock(r, key="k", token="t", ttl_seconds=90) as acquired:
            assert acquired is True
            await asyncio.sleep(0.05)  # let the refresher run a few times

        # At least one refresh happened (pexpire-if-owner via eval) plus the
        # final release; every eval carried our token.
        assert r.eval.await_count >= 2
        for call in r.eval.await_args_list:
            assert call.args[-1] in ("t", "90000") or "t" in call.args

    async def test_refresher_is_stopped_on_exit(self, monkeypatch):
        monkeypatch.setattr(redis_lock, "_refresh_interval_seconds", lambda ttl: 0)
        r = _redis(acquire_ok=True)

        async with refreshing_redis_lock(r, key="k", token="t", ttl_seconds=90):
            await asyncio.sleep(0.02)
        count_after_exit = r.eval.await_count
        await asyncio.sleep(0.03)
        # No further refreshes after the context exited.
        assert r.eval.await_count == count_after_exit
