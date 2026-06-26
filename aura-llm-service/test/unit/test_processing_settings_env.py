"""Regression test for the processing settings env_file fix: an env override
with the right prefix must actually reach the setting. Before the fix the four
classes pointed env_file at a non-existent app/.env, so overrides placed in the
real .env were silently ignored. Here we assert OS-env overrides take effect."""
from app.application.services.processing.document_classify_service.document_classify_settings import (
    DocumentClassifyServiceSettings,
)
from app.application.services.processing.fragment_contextualize_service.fragment_contextualize_settings import (
    FragmentContextualizeServiceSettings,
)
from app.application.services.processing.graph_extraction_service.graph_extraction_settings import (
    GraphExtractionServiceSettings,
)
from app.application.services.processing.graph_query_translation_service.graph_query_translation_settings import (
    GraphQueryTranslationServiceSettings,
)


def test_document_classify_env_override_applies(monkeypatch):
    monkeypatch.setenv("DOCUMENT_CLASSIFY_MAX_CONTENT_CHARS", "12345")
    assert DocumentClassifyServiceSettings().max_content_chars == 12345


def test_fragment_contextualize_env_override_applies(monkeypatch):
    monkeypatch.setenv("FRAGMENT_CONTEXTUALIZE_MAX_CONTENT_CHARS", "11000")
    assert FragmentContextualizeServiceSettings().max_content_chars == 11000


def test_graph_extraction_env_overrides_apply(monkeypatch):
    monkeypatch.setenv("GRAPH_EXTRACTION_MAX_REPAIR_ATTEMPTS", "3")
    monkeypatch.setenv("GRAPH_EXTRACTION_MIN_RELATION_CONFIDENCE", "0.7")
    settings = GraphExtractionServiceSettings()
    assert settings.max_repair_attempts == 3
    assert settings.min_relation_confidence == 0.7


def test_graph_query_translation_env_override_applies(monkeypatch):
    monkeypatch.setenv("GRAPH_QUERY_TRANSLATION_MAX_REPAIR_ATTEMPTS", "0")
    assert GraphQueryTranslationServiceSettings().max_repair_attempts == 0


def test_gpu_defaults_when_no_env(monkeypatch):
    for var in (
        "DOCUMENT_CLASSIFY_MAX_CONTENT_CHARS",
        "GRAPH_EXTRACTION_MAX_REPAIR_ATTEMPTS",
        "GRAPH_QUERY_TRANSLATION_MAX_REPAIR_ATTEMPTS",
    ):
        monkeypatch.delenv(var, raising=False)
    assert DocumentClassifyServiceSettings(_env_file=None).max_content_chars == 60_000
    assert GraphExtractionServiceSettings(_env_file=None).max_repair_attempts == 2
    assert GraphQueryTranslationServiceSettings(_env_file=None).max_repair_attempts == 2
