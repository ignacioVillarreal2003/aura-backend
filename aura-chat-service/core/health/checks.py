"""Dependency probes for readiness/startup, kept out of the HTTP layer so they
can be reused and unit-tested without a request."""
import logging
from dataclasses import dataclass

from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool


def check_database() -> CheckResult:
    try:
        connection.ensure_connection()
        return CheckResult("database", True)
    except Exception:
        logger.warning("Readiness check: database unreachable.", exc_info=True)
        return CheckResult("database", False)


def check_redis() -> CheckResult:
    try:
        cache.set("_healthcheck", "ok", timeout=5)
        return CheckResult("redis", True)
    except Exception:
        logger.warning("Readiness check: Redis unreachable.", exc_info=True)
        return CheckResult("redis", False)


def dependency_checks() -> list[CheckResult]:
    """Every external dependency this service needs to serve traffic."""
    return [check_database(), check_redis()]
