"""Real HuggingFaceTextSplitter on CPU (downloads small embedding model on first run).

Requires: torch, sentence_transformers, langchain_experimental, langchain_huggingface.

Enable with: RUN_SLOW=1 pytest tests/unit/text_splitters/test_huggingface_text_splitter_slow.py
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow

pytest.importorskip("torch")
pytest.importorskip("sentence_transformers")
pytest.importorskip("langchain_experimental")
pytest.importorskip("langchain_huggingface")

from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.instances.huggingface_text_splitter import HuggingFaceTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


def _cpu_settings(**kwargs: object) -> TextSplitterSettings:
    base: dict = dict(
        active_type=TextSplitterType.huggingface,
        huggingface_model="sentence-transformers/all-MiniLM-L6-v2",
        huggingface_device="cpu",
        huggingface_breakpoint_threshold_type="percentile",
        huggingface_breakpoint_threshold_amount=0.8,
        recursive_split_size=512,
        recursive_split_overlap=50,
        markdown_processor_split_size=512,
        markdown_processor_split_overlap=50,
        max_text_length=100_000,
    )
    base.update(kwargs)
    return TextSplitterSettings(**base)


@pytest.fixture(scope="module")
def real_hf_splitter() -> HuggingFaceTextSplitter:
    """One load per module to amortize model download and init."""
    return HuggingFaceTextSplitter(_cpu_settings())


def test_real_split_produces_nonempty_chunks(real_hf_splitter: HuggingFaceTextSplitter) -> None:
    text = (
        "Physics describes matter, energy, and fundamental forces in nature. " * 12
        + "\n\n"
        + "Culinary arts focus on ingredients, techniques, and flavor combinations. " * 12
    )
    chunks = real_hf_splitter.split_text(text)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    assert all(isinstance(c, str) for c in chunks)
    joined = "\n".join(chunks)
    assert "Physics" in joined or "Culinary" in joined
    assert any(c.strip() for c in chunks)


def test_real_split_empty_returns_empty_list(real_hf_splitter: HuggingFaceTextSplitter) -> None:
    assert real_hf_splitter.split_text("") == []
    assert real_hf_splitter.split_text("  \n  ") == []
