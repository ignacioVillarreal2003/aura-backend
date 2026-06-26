import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import FastAPI

logger = logging.getLogger(__name__)

_CleanupFn = Callable[[], Awaitable[None]]

_CLEANUPS_STATE_ATTR = "_dependency_cleanups"


class DependencyRegistry:
    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._registered: list[str] = []
        self._cleanups: list[tuple[str, _CleanupFn]] = []

    def register(self, name: str, instance: Any, cleanup: _CleanupFn | None = None) -> None:
        setattr(self._app.state, name, instance)
        self._registered.append(name)
        if cleanup is not None:
            self._cleanups.append((name, cleanup))

    def commit(self) -> None:
        setattr(self._app.state, _CLEANUPS_STATE_ATTR, list(self._cleanups))
        self._registered.clear()
        self._cleanups.clear()

    async def rollback(self) -> None:
        while self._cleanups:
            name, cleanup = self._cleanups.pop()
            try:
                await cleanup()
            except Exception:
                logger.exception(
                    "Startup rollback: cleanup step failed (continuing with remaining steps).",
                    extra={"resource": name},
                )

        for name in reversed(self._registered):
            if hasattr(self._app.state, name):
                delattr(self._app.state, name)
        self._registered.clear()


async def run_committed_cleanups(app: FastAPI) -> None:
    cleanups: list[tuple[str, _CleanupFn]] = getattr(app.state, _CLEANUPS_STATE_ATTR, None) or []
    for name, cleanup in reversed(cleanups):
        try:
            await cleanup()
        except Exception:
            logger.exception(
                "Shutdown: cleanup step failed (continuing with remaining steps).",
                extra={"resource": name},
            )
    if hasattr(app.state, _CLEANUPS_STATE_ATTR):
        delattr(app.state, _CLEANUPS_STATE_ATTR)
