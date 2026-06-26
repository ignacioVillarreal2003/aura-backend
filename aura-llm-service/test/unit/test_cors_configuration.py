"""Unit tests for configure_cors: a wildcard origin must disable credentials
(browsers reject `*` + credentials), while explicit origins enable them."""
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

import app.configuration.cors_configuration as cors_module


class _FakeSettings:
    def __init__(self, origins: list[str]) -> None:
        self.cors_origins = origins


def _cors_kwargs(app: FastAPI) -> dict:
    for mw in app.user_middleware:
        if mw.cls is CORSMiddleware:
            return getattr(mw, "kwargs", None) or getattr(mw, "options", {})
    raise AssertionError("CORS middleware was not registered")


def test_explicit_origins_enable_credentials(monkeypatch):
    monkeypatch.setattr(cors_module, "get_settings", lambda: _FakeSettings(["http://a", "http://b"]))
    app = FastAPI()
    cors_module.configure_cors(app)
    kwargs = _cors_kwargs(app)
    assert kwargs["allow_credentials"] is True
    assert kwargs["allow_origins"] == ["http://a", "http://b"]


def test_wildcard_origin_disables_credentials(monkeypatch):
    monkeypatch.setattr(cors_module, "get_settings", lambda: _FakeSettings(["*"]))
    app = FastAPI()
    cors_module.configure_cors(app)
    assert _cors_kwargs(app)["allow_credentials"] is False


def test_wildcard_mixed_with_real_origin_still_disables_credentials(monkeypatch):
    monkeypatch.setattr(cors_module, "get_settings", lambda: _FakeSettings(["http://a", "*"]))
    app = FastAPI()
    cors_module.configure_cors(app)
    assert _cors_kwargs(app)["allow_credentials"] is False
