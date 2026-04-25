from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/health",
        "/metrics",
    }
)

_HTTP_BEARER = "HTTPBearer"


def _get_openapi_kwargs(app: FastAPI) -> dict:
    kwargs: dict = {
        "title": app.title,
        "version": app.version,
        "openapi_version": app.openapi_version,
        "description": app.description,
        "routes": app.routes,
    }
    if getattr(app, "summary", None) is not None:
        kwargs["summary"] = app.summary
    if getattr(app, "openapi_tags", None) is not None:
        kwargs["tags"] = app.openapi_tags
    if getattr(app, "servers", None) is not None:
        kwargs["servers"] = app.servers
    for key in ("terms_of_service", "contact", "license_info"):
        v = getattr(app, key, None)
        if v is not None:
            kwargs[key] = v
    if hasattr(app, "separate_input_output_schemas"):
        kwargs["separate_input_output_schemas"] = app.separate_input_output_schemas
    _wh = getattr(app, "webhooks", None)
    if _wh is not None:
        wh_routes = getattr(_wh, "routes", _wh)
        if wh_routes:
            kwargs["webhooks"] = wh_routes
    return kwargs


def _attach_bearer_scheme(openapi_schema: dict) -> None:
    components = openapi_schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})
    schemes[_HTTP_BEARER] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Pega el token: se envía como cabecera Authorization: Bearer <token>.",
    }


def _apply_bearer_to_paths(openapi_schema: dict) -> None:
    for path, path_item in (openapi_schema.get("paths") or {}).items():
        for method in ("get", "post", "put", "delete", "patch", "head", "options", "trace"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            if path in _PUBLIC_PATHS:
                operation["security"] = []
            else:
                operation["security"] = [{_HTTP_BEARER: []}]


def install_openapi_bearer(app: FastAPI) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema is not None:
            return app.openapi_schema
        openapi_schema = get_openapi(**_get_openapi_kwargs(app))
        _attach_bearer_scheme(openapi_schema)
        _apply_bearer_to_paths(openapi_schema)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
