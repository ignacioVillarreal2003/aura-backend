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

    max_concurrency: int = Field(
        default=4,
        ge=1,
        le=256,
        description=(
            "Max simultaneous LLM calls PER WORKER. Effective deployment ceiling "
            "is WEB_CONCURRENCY * this value; scale down when adding workers."
        ),
    )


_settings: Optional[LLMConcurrencySettings] = None
_semaphore: Optional[asyncio.Semaphore] = None
_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_settings() -> LLMConcurrencySettings:
    global _settings
    if _settings is None:
        _settings = LLMConcurrencySettings()
    return _settings


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        max_concurrency = _get_settings().max_concurrency
        _semaphore = asyncio.Semaphore(max_concurrency)
        _semaphore_loop = loop
        logger.info("LLM concurrency limiter initialized.", extra={"max_concurrency": max_concurrency})
    return _semaphore


@asynccontextmanager
async def llm_slot() -> AsyncIterator[None]:
    semaphore = _get_semaphore()
    await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()
