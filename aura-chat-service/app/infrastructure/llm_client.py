import httpx

from app.configuration.environment_variables import settings
from app.application.exceptions.api_exceptions import LLMError


class LLMClient:
    """Async HTTP client for the aura-llm-service /api/agent endpoint."""

    async def call_agent(self, messages: list[dict], token: str) -> str:
        """
        Send a conversation history to the LLM agent and return the reply text.

        messages: list of {"role": "human"|"assistant", "content": "..."}
        token: Bearer token forwarded from the original request.
        """
        try:
            async with httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS)) as client:
                response = await client.post(
                    f"{settings.LLM_SERVICE_URL}/api/agent",
                    json={"messages": messages},
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                return response.json()["message"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"LLM service returned {e.response.status_code}: {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise LLMError(f"Could not reach LLM service: {e}")


# Module-level singleton used by MessageService by default
llm_client = LLMClient()
