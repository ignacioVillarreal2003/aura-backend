import logging
import httpx
from django.conf import settings
from .exceptions import LLMError

logger = logging.getLogger(__name__)


class LLMClient:
    def call_agent(self, messages: list[dict], token: str) -> str:
        url = f'{settings.LLM_SERVICE_URL}/api/agent'
        headers = {'Authorization': f'Bearer {token}'}
        payload = {'messages': messages}

        try:
            with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()['message']
        except httpx.HTTPStatusError as e:
            logger.error(f'LLM service error: {e.response.status_code} - {e.response.text}')
            raise LLMError(f'LLM service returned {e.response.status_code}')
        except Exception as e:
            logger.error(f'LLM client error: {e}')
            raise LLMError(str(e))


llm_client = LLMClient()
