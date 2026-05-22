import threading
from langchain_huggingface import HuggingFaceEmbeddings

_lock = threading.Lock()
_cache: dict[tuple[str, str, bool], HuggingFaceEmbeddings] = {}


def get_or_create(
        model_name: str,
        device: str,
        normalize_embeddings: bool = True,
) -> HuggingFaceEmbeddings:
    key = (model_name, device, normalize_embeddings)
    if key in _cache:
        return _cache[key]
    with _lock:
        if key not in _cache:
            _cache[key] = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": normalize_embeddings},
            )
        return _cache[key]
