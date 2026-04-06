"""
Optional full ingestion pipeline (document -> chunks -> embeddings -> DB).

Placeholder: implement E2E against Docker when migrations, Ollama/embedder and MinIO paths are stable.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.asyncio
async def test_full_document_ingestion_pipeline_placeholder() -> None:
    pytest.skip(
        "Optional E2E: wire DocumentIngestionService with real stack (set RUN_INTEGRATION=1 when implemented)."
    )
