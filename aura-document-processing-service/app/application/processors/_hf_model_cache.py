import logging
import threading
from typing import Optional
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

_lock = threading.Lock()

_cache: dict[
    tuple[str, str, bool, Optional[str], Optional[int]],
    tuple[HuggingFaceEmbeddings, threading.Lock],
] = {}


def get_or_create(
        model_name: str,
        device: str,
        normalize_embeddings: bool = True,
        token: str | None = None,
        max_seq_length: Optional[int] = None,
) -> tuple[HuggingFaceEmbeddings, threading.Lock]:
    key = (model_name, device, normalize_embeddings, token, max_seq_length)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    with _lock:
        cached = _cache.get(key)
        if cached is None:
            model_kwargs: dict = {"device": device}
            if token:
                model_kwargs["token"] = token
            embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs={"normalize_embeddings": normalize_embeddings},
            )
            if max_seq_length is not None:
                try:
                    embeddings.client.max_seq_length = max_seq_length
                except Exception:
                    logger.warning(
                        "Could not apply the configured max_seq_length to the model; "
                        "keeping the model default.",
                        extra={"model_name": model_name, "max_seq_length": max_seq_length},
                    )
            cached = (embeddings, threading.Lock())
            _cache[key] = cached
        return cached
