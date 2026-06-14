"""Health probes — liveness / readiness / startup.

Verifies failure semantics (liveness never touches dependencies; readiness/startup
return 503 when a dependency is down), no-auth access, and the backward-compatible
`/api/v1/health` alias.
"""
from core.health.checks import CheckResult

HEALTH_VIEWS = "core.health.views"


def _patch_checks(mocker, *results):
    return mocker.patch(f"{HEALTH_VIEWS}.dependency_checks", return_value=list(results))


def test_liveness_ok_without_auth_or_dependencies(anon_client, mocker):
    deps = mocker.patch(f"{HEALTH_VIEWS}.dependency_checks")
    response = anon_client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.data["status"] == "alive"
    deps.assert_not_called()  # liveness must not perform dependency I/O


def test_readiness_200_when_all_dependencies_up(anon_client, mocker):
    _patch_checks(mocker, CheckResult("database", True), CheckResult("redis", True))
    response = anon_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.data == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


def test_readiness_503_when_a_dependency_is_down(anon_client, mocker):
    _patch_checks(mocker, CheckResult("database", True), CheckResult("redis", False))
    response = anon_client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.data["status"] == "not_ready"
    assert response.data["checks"] == {"database": "ok", "redis": "error"}


def test_startup_uses_dependency_checks(anon_client, mocker):
    _patch_checks(mocker, CheckResult("database", False), CheckResult("redis", True))
    response = anon_client.get("/api/v1/health/startup")
    assert response.status_code == 503


def test_legacy_health_path_aliases_readiness(anon_client, mocker):
    _patch_checks(mocker, CheckResult("database", True), CheckResult("redis", True))
    response = anon_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.data["status"] == "ready"
