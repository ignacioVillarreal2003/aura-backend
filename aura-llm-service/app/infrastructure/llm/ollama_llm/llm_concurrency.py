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
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_settings.max_concurrency)
        logger.info("LLM concurrency limiter initialized.", extra={"max_concurrency": _settings.max_concurrency})
    return _semaphore


@asynccontextmanager
async def llm_slot() -> AsyncIterator[None]:
    semaphore = _get_semaphore()
    await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()
