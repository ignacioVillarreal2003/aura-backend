import pytest

from core.clients.exceptions import HttpClientException
from core.clients.llm_client import LLMClient


def test_require_configured_url_rejects_blank():
    with pytest.raises(HttpClientException) as exc_info:
        LLMClient._require_configured_url("   ", "timeline-generate")
    assert exc_info.value.status_code == 503
    assert "timeline-generate" in str(exc_info.value)


def test_require_configured_url_accepts_non_empty():
    LLMClient._require_configured_url("http://llm.example/generate", "timeline-generate")
