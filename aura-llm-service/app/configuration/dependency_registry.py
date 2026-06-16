import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import FastAPI

logger = logging.getLogger(__name__)

_CleanupFn = Callable[[], Awaitable[None]]


class DependencyRegistry:
    """Tracks dependencies registered on ``app.state`` during startup so that a
    failure partway through can be rolled back: cleanups run in reverse order and
    state attributes are removed. ``commit`` hands ownership to the app, after
    which ``rollback`` is a no-op."""

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
