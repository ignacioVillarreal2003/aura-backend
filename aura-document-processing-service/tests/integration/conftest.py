"""
Integration tests: run with RUN_INTEGRATION=1 and Docker from aura-backend/docker/docker-compose.yml
(`docker compose up -d db storage queue`).
"""

from __future__ import annotations

import os


def integration_async_database_url() -> str:
    return os.environ.get(
        "INTEGRATION_ASYNC_DATABASE_URL",
        "postgresql+asyncpg://aura_root:aura_password@127.0.0.1:5432/aura_db",
    )


def integration_rabbitmq_url() -> str:
    return os.environ.get(
        "INTEGRATION_RABBITMQ_URL",
        "amqp://aura_root:aura_password@127.0.0.1:5672/",
    )
