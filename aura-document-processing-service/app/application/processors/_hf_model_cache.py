import threading
from langchain_huggingface import HuggingFaceEmbeddings

_lock = threading.Lock()
_cache: dict[tuple[str, str, bool, str | None], HuggingFaceEmbeddings] = {}


def get_or_create(
        model_name: str,
        device: str,
        normalize_embeddings: bool = True,
        token: str | None = None,
) -> HuggingFaceEmbeddings:
    key = (model_name, device, normalize_embeddings, token)
    if key in _cache:
        return _cache[key]
    with _lock:
        if key not in _cache:
            model_kwargs: dict = {"device": device}
            if token:
                model_kwargs["token"] = token
            _cache[key] = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs={"normalize_embeddings": normalize_embeddings},
            )
        return _cache[key]
