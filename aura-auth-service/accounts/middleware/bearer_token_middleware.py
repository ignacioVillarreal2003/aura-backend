"""Middleware that captures the incoming Bearer token into a ContextVar.

This runs before DRF authentication so that outbound HTTP clients can
forward the user's JWT to downstream services without needing the request
object threaded through every layer.
"""
from __future__ import annotations

from accounts.request_token import reset_request_token, set_request_token


class BearerTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = self._extract_token(request)
        if token:
            ctx = set_request_token(token)
            try:
                return self.get_response(request)
            finally:
                reset_request_token(ctx)
        return self.get_response(request)

    @staticmethod
    def _extract_token(request) -> str | None:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            bearer = f"Bearer {parts[1]}"
            return bearer
        return None
