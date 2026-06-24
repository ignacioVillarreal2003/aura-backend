"""Half-precision dtype resolution for the Hugging Face embedder loader.

fp16/bfloat16 are CUDA-only optimizations; on CPU the loader must fall back to
full precision, and "float32"/None must never inject a torch_dtype override.
"""
from app.application.processors._hf_model_cache import _resolve_effective_dtype


class TestResolveEffectiveDtype:
    def test_float16_on_cuda_is_applied(self):
        assert _resolve_effective_dtype("float16", "cuda") == "float16"

    def test_bfloat16_on_cuda_is_applied(self):
        assert _resolve_effective_dtype("bfloat16", "cuda") == "bfloat16"

    def test_half_precision_on_cpu_falls_back_to_full(self):
        assert _resolve_effective_dtype("float16", "cpu") is None

    def test_float32_is_no_override(self):
        assert _resolve_effective_dtype("float32", "cuda") is None

    def test_none_is_no_override(self):
        assert _resolve_effective_dtype(None, "cuda") is None
