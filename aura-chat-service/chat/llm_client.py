"""HTTP client for the aura-llm-service /api/v1/agent endpoint.

Provides both a synchronous variant (for regular DRF views) and an
asynchronous variant (for the SSE streaming view running under ASGI).
"""

import logging

import httpx
from django.conf import settings

from .exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMClient:
    # ------------------------------------------------------------------ sync

    def call_agent(self, messages: list[dict], token: str) -> str:
        """Blocking call; suitable for use in synchronous DRF views."""
        try:
            with httpx.Client(timeout=float(settings.LLM_TIMEOUT_SECONDS)) as client:
                response = client.post(
                    f"{settings.LLM_SERVICE_URL}/api/v1/agent",
                    json={"messages": messages},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                return response.json()["message"]
        except httpx.HTTPStatusError as exc:
            logger.error("LLM service HTTP error: %s — %s", exc.response.status_code, exc.response.text[:200])
            raise LLMError(f"LLM service returned {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("LLM service unreachable: %s", exc)
            raise LLMError(f"Could not reach LLM service: {exc}")

    # ----------------------------------------------------------------- async

    async def call_agent_async(self, messages: list[dict], token: str) -> str:
        """Non-blocking call; suitable for use in async views (ASGI / SSE)."""
        try:
            async with httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS)) as client:
                response = await client.post(
                    f"{settings.LLM_SERVICE_URL}/api/v1/agent",
                    json={"messages": messages},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                return response.json()["message"]
        except httpx.HTTPStatusError as exc:
            logger.error("LLM service HTTP error: %s — %s", exc.response.status_code, exc.response.text[:200])
            raise LLMError(f"LLM service returned {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("LLM service unreachable: %s", exc)
            raise LLMError(f"Could not reach LLM service: {exc}")


# Module-level singleton used by both service classes.
llm_client = LLMClient()
