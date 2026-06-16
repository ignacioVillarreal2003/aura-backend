"""Process-wide concurrency limit for LLM calls (A4).

A single Ollama instance can only run so many generations at once; without a
bound, N concurrent requests all hit it and latency collapses. This caps the
number of in-flight LLM calls per worker process. With multiple web workers the
effective global limit is ``workers * LLM_MAX_CONCURRENCY`` — keep workers at 1
for a hard global cap, or size the product to the Ollama server's capacity.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class LLMConcurrencySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_concurrency: int = Field(default=4, ge=1, le=256)


_settings = LLMConcurrencySettings()
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    # Created lazily on first use so it binds to the running event loop.
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_settings.max_concurrency)
        logger.info("LLM concurrency limiter initialized.", extra={"max_concurrency": _settings.max_concurrency})
    return _semaphore


@asynccontextmanager
async def llm_slot() -> AsyncIterator[None]:
    """Acquire one of the limited LLM execution slots for the duration of a call
    (or a full stream). Released automatically on exit, error or early close."""
    semaphore = _get_semaphore()
    await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()
