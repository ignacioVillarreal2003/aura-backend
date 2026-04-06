"""PostgreSQL connectivity (Docker `db` service)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.conftest import integration_async_database_url

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_select_one() -> None:
    engine = create_async_engine(integration_async_database_url())
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 AS n"))
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()
