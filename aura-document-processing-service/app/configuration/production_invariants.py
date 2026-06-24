import logging
from urllib.parse import unquote, urlparse

from app.configuration.environment_variables import environment_variables
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import (
    RabbitMQManagerSettings,
)
from app.infrastructure.persistence.database.database_manager.database_manager_settings import (
    DatabaseManagerSettings,
)
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager_settings import (
    Neo4jManagerSettings,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import (
    RedisClientSettings,
)
from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import (
    MinioManagerSettings,
)

logger = logging.getLogger(__name__)

_WEAK_SECRETS = frozenset(
    {
        "",
        "postgres",
        "password",
        "passwd",
        "admin",
        "root",
        "changeme",
        "secret",
        "test",
        "guest",
        "minioadmin",
        "minio",
        "redis",
        "neo4j",
        "rabbitmq",
    }
)

_DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/0"


class ProductionInvariantError(RuntimeError):
    pass


def assert_production_invariants() -> None:
    if not environment_variables.is_production():
        return

    violations: list[str] = []
    _check_runtime_flags(violations)
    _check_database(violations)
    _check_redis(violations)
    _check_minio(violations)
    _check_neo4j(violations)
    _check_rabbitmq(violations)

    if violations:
        bullet_list = "\n".join(f"  - {violation}" for violation in violations)
        raise ProductionInvariantError(
            "Refusing to start in production "
            f"(ENVIRONMENT='{environment_variables.environment}') due to unsafe "
            f"configuration:\n{bullet_list}"
        )

    logger.info("Production invariants verified: configuration is safe for production.")


def _check_runtime_flags(violations: list[str]) -> None:
    if environment_variables.app_reload:
        violations.append(
            "APP_RELOAD must be False in production (hot-reload watches source files "
            "and is not safe for a production deployment)."
        )

    if environment_variables.log_level == "DEBUG":
        violations.append(
            "LOG_LEVEL must not be DEBUG in production (verbose logs may leak sensitive data)."
        )

    if any((origin or "").strip() == "*" for origin in environment_variables.cors_origins):
        violations.append(
            "CORS_ORIGINS must not contain '*' in production; specify explicit origins."
        )


def _check_database(violations: list[str]) -> None:
    settings = DatabaseManagerSettings()

    if settings.echo_sql:
        violations.append(
            "DATABASE_MANAGER_ECHO_SQL must be False in production "
            "(echoes every SQL statement, including parameter values)."
        )

    if settings.query_logging_enabled:
        violations.append(
            "DATABASE_MANAGER_QUERY_LOGGING_ENABLED must be False in production."
        )

    _check_secret(
        violations,
        env_name="DATABASE_MANAGER_PASSWORD",
        value=settings.password.get_secret_value(),
    )


def _check_redis(violations: list[str]) -> None:
    settings = RedisClientSettings()
    url = settings.url.get_secret_value()

    if url.strip() == _DEFAULT_REDIS_URL:
        violations.append(
            "REDIS_CLIENT_URL must be set explicitly in production "
            "(still pointing at the unauthenticated localhost default)."
        )


def _check_minio(violations: list[str]) -> None:
    settings = MinioManagerSettings()

    _check_secret(
        violations,
        env_name="MINIO_MANAGER_SECRET_KEY",
        value=settings.secret_key.get_secret_value(),
    )

    if settings.access_key.strip().lower() in _WEAK_SECRETS:
        violations.append(
            "MINIO_MANAGER_ACCESS_KEY is a well-known default and must be changed in production."
        )

    if not settings.use_tls:
        violations.append(
            "MINIO_MANAGER_USE_TLS must be True in production (object storage traffic "
            "would otherwise be unencrypted)."
        )


def _check_neo4j(violations: list[str]) -> None:
    settings = Neo4jManagerSettings()

    _check_secret(
        violations,
        env_name="NEO4J_MANAGER_PASSWORD",
        value=settings.password.get_secret_value(),
    )

    scheme = (urlparse(settings.uri).scheme or "").lower()
    scheme_encrypted = scheme in ("neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc")
    if not scheme_encrypted and settings.encrypted is not True:
        violations.append(
            "Neo4j must use an encrypted connection in production: use a +s/+ssc URI "
            "scheme (e.g. neo4j+s://) or set NEO4J_MANAGER_ENCRYPTED=True."
        )


def _check_rabbitmq(violations: list[str]) -> None:
    settings = RabbitMQManagerSettings()
    parsed = urlparse(settings.url.get_secret_value())

    if (parsed.scheme or "").lower() != "amqps":
        violations.append(
            "RABBITMQ_MANAGER_URL must use amqps:// (TLS) in production; "
            "amqp:// sends credentials and messages unencrypted."
        )

    password = unquote(parsed.password) if parsed.password else ""
    if password.strip().lower() in _WEAK_SECRETS:
        violations.append(
            "RABBITMQ_MANAGER_URL embeds an empty or well-known weak password "
            "(e.g. guest); use strong broker credentials in production."
        )


def _check_secret(violations: list[str], *, env_name: str, value: str) -> None:
    if value.strip().lower() in _WEAK_SECRETS:
        violations.append(
            f"{env_name} is empty or a well-known weak credential and must be changed in production."
        )
