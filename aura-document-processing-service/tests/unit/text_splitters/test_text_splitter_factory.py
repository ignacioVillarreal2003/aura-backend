import pytest
from unittest.mock import MagicMock

pytest.importorskip("tiktoken")

import app.application.processors.text_splitters.instances.huggingface_text_splitter as hf_splitter_mod
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    UnsupportedTextSplitterTypeException,
)
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


def _base_kwargs() -> dict:
    return dict(
        recursive_split_size=120,
        recursive_split_overlap=20,
        markdown_processor_split_size=120,
        markdown_processor_split_overlap=20,
    )


def test_is_supported_and_available_types() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    assert factory.is_supported(TextSplitterType.recursive)
    assert factory.is_supported(TextSplitterType.markdown_processor)
    assert TextSplitterType.recursive in factory.available_types()


def test_get_by_type_recursive() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    sp = factory.get_by_type(TextSplitterType.recursive)
    chunks = sp.split_text("x " * 200)
    assert len(chunks) >= 1


def test_get_by_type_invalid_raises() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    with pytest.raises(UnsupportedTextSplitterTypeException):
        factory.get_by_type(object())  # type: ignore[arg-type]


def test_get_active_type() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.markdown_processor, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    assert factory.get_active_type() == TextSplitterType.markdown_processor


def test_splitter_property_returns_cached_instance() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    s1 = factory.splitter
    s2 = factory.splitter
    assert s1 is s2


def test_get_by_type_markdown_splits_long_text() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    sp = factory.get_by_type(TextSplitterType.markdown_processor)
    chunks = sp.split_text("# T\n\n" + ("word " * 200))
    assert len(chunks) >= 1


def test_is_supported_huggingface_in_available_types() -> None:
    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    assert factory.is_supported(TextSplitterType.huggingface) is True
    assert TextSplitterType.huggingface in factory.available_types()


def test_get_by_type_huggingface_with_mocked_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_chunker = MagicMock()
    mock_chunker.split_text.return_value = ["chunk_a"]
    monkeypatch.setattr(hf_splitter_mod, "HuggingFaceEmbeddings", MagicMock())
    monkeypatch.setattr(hf_splitter_mod, "SemanticChunker", MagicMock(return_value=mock_chunker))

    settings = TextSplitterSettings(active_type=TextSplitterType.recursive, **_base_kwargs())
    factory = TextSplitterFactory(text_splitter_settings=settings)
    sp = factory.get_by_type(TextSplitterType.huggingface)
    assert sp.split_text("some semantic text to split") == ["chunk_a"]
    mock_chunker.split_text.assert_called_once()
