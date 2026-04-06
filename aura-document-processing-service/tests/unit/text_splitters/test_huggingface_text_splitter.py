"""Unit tests for HuggingFaceTextSplitter (SemanticChunker + embeddings mocked)."""

from unittest.mock import MagicMock

import pytest

import app.application.processors.text_splitters.instances.huggingface_text_splitter as hf_splitter_mod
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterExecutionException,
    TextSplitterInitializationException,
)
from app.application.processors.text_splitters.instances.huggingface_text_splitter import HuggingFaceTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


def _hf_settings(**kwargs) -> TextSplitterSettings:
    base: dict = dict(
        active_type=TextSplitterType.huggingface,
        recursive_split_size=512,
        recursive_split_overlap=50,
        markdown_processor_split_size=512,
        markdown_processor_split_overlap=50,
        max_text_length=10_000,
    )
    base.update(kwargs)
    return TextSplitterSettings(**base)


@pytest.fixture
def mock_hf_splitter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[HuggingFaceTextSplitter, MagicMock, MagicMock, MagicMock]:
    mock_embed_cls = MagicMock()
    mock_chunker_instance = MagicMock()
    mock_chunker_instance.split_text.return_value = ["part one", "part two"]
    mock_chunker_cls = MagicMock(return_value=mock_chunker_instance)
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", mock_embed_cls)
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", mock_chunker_cls)
    splitter = HuggingFaceTextSplitter(_hf_settings())
    return splitter, mock_chunker_instance, mock_embed_cls, mock_chunker_cls


def test_init_builds_embeddings_and_semantic_chunker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_embed_cls = MagicMock()
    mock_chunker_instance = MagicMock()
    mock_chunker_cls = MagicMock(return_value=mock_chunker_instance)
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", mock_embed_cls)
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", mock_chunker_cls)

    settings = _hf_settings(
        huggingface_model="sentence-transformers/all-MiniLM-L6-v2",
        huggingface_device="cpu",
        huggingface_breakpoint_threshold_type="percentile",
        huggingface_breakpoint_threshold_amount=0.5,
    )
    HuggingFaceTextSplitter(settings)

    mock_embed_cls.assert_called_once()
    call_kw = mock_embed_cls.call_args.kwargs
    assert call_kw["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert call_kw["model_kwargs"] == {"device": "cpu"}

    mock_chunker_cls.assert_called_once()
    chunker_kw = mock_chunker_cls.call_args.kwargs
    assert chunker_kw["breakpoint_threshold_type"] == "percentile"
    assert chunker_kw["breakpoint_threshold_amount"] == 0.5


def test_init_omits_breakpoint_amount_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_embed_cls = MagicMock()
    mock_chunker_cls = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", mock_embed_cls)
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", mock_chunker_cls)

    HuggingFaceTextSplitter(_hf_settings(huggingface_breakpoint_threshold_amount=None))

    chunker_kw = mock_chunker_cls.call_args.kwargs
    assert "breakpoint_threshold_amount" not in chunker_kw
    assert chunker_kw["breakpoint_threshold_type"] == "percentile"


def test_init_failure_raises_initialization_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", MagicMock(side_effect=RuntimeError("load failed")))
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", MagicMock())

    with pytest.raises(TextSplitterInitializationException):
        HuggingFaceTextSplitter(_hf_settings())


def test_split_empty_returns_empty_list(mock_hf_splitter: tuple) -> None:
    splitter, chunker, _, _ = mock_hf_splitter
    assert splitter.split_text("") == []
    assert splitter.split_text("   \n\t  ") == []
    chunker.split_text.assert_not_called()


def test_split_exceeds_max_text_length_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", MagicMock())
    mock_chunker = MagicMock()
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", MagicMock(return_value=mock_chunker))
    splitter = HuggingFaceTextSplitter(_hf_settings(max_text_length=10))
    with pytest.raises(TextSplitterExecutionException):
        splitter.split_text("x" * 11)
    mock_chunker.split_text.assert_not_called()


def test_split_delegates_to_semantic_chunker(mock_hf_splitter: tuple) -> None:
    splitter, chunker, _, _ = mock_hf_splitter
    text = "some longer body " * 5
    out = splitter.split_text(text)
    assert out == ["part one", "part two"]
    chunker.split_text.assert_called_once_with(text)


def test_split_chunker_runtime_error_wraps_execution_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_chunker = MagicMock()
    mock_chunker.split_text.side_effect = RuntimeError("chunk failed")
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", MagicMock())
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", MagicMock(return_value=mock_chunker))
    splitter = HuggingFaceTextSplitter(_hf_settings())

    with pytest.raises(TextSplitterExecutionException):
        splitter.split_text("not empty")
