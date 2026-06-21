import argparse
import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("download_models")

RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 10

_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _is_transient(exc: BaseException) -> bool:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        return status in _RETRYABLE_STATUS
    return True


def _with_retries(label: str, fn) -> None:
    for attempt in range(1, RETRIES + 1):
        try:
            started = time.monotonic()
            fn()
            logger.info("Ready: %s (%.1fs)", label, time.monotonic() - started)
            return
        except Exception as exc:
            if not _is_transient(exc):
                logger.error("Non-retryable error for %s: %s", label, exc)
                raise
            logger.exception("Attempt %d/%d failed: %s", attempt, RETRIES, label)
            if attempt == RETRIES:
                raise
            time.sleep(RETRY_BASE_DELAY_SECONDS * attempt)


def download_sentence_transformer(model_name: str) -> None:
    from sentence_transformers import SentenceTransformer

    _with_retries(
        f"sentence-transformer '{model_name}'",
        lambda: SentenceTransformer(model_name, device="cpu"),
    )


def download_cross_encoder(model_name: str) -> None:
    from sentence_transformers import CrossEncoder

    _with_retries(
        f"cross-encoder '{model_name}'",
        lambda: CrossEncoder(model_name, device="cpu"),
    )


def download_tiktoken_encoding(encoding_name: str) -> None:
    import tiktoken

    _with_retries(
        f"tiktoken encoding '{encoding_name}'",
        lambda: tiktoken.get_encoding(encoding_name),
    )


def download_docling_models(output_dir: str) -> None:
    from pathlib import Path

    from docling.utils.model_downloader import download_models

    _with_retries(
        f"docling models -> '{output_dir}'",
        lambda: download_models(output_dir=Path(output_dir)),
    )


def _clean(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.append(value)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sentence-transformer",
        action="append",
        default=[],
        help="Sentence-transformer model to pre-download (repeatable; empty values are skipped).",
    )
    parser.add_argument(
        "--cross-encoder",
        action="append",
        default=[],
        help="Cross-encoder (reranker) model to pre-download (repeatable; empty values are skipped).",
    )
    parser.add_argument(
        "--tiktoken",
        action="append",
        default=[],
        help="tiktoken encoding to pre-download (repeatable; empty values are skipped).",
    )
    parser.add_argument(
        "--docling-output",
        default="",
        help="Directory to pre-download Docling's models (layout/tableformer) into; empty skips.",
    )
    args = parser.parse_args()

    sentence_transformers = _clean(args.sentence_transformer)
    cross_encoders = _clean(args.cross_encoder)
    tiktoken_encodings = _clean(args.tiktoken)
    docling_output = args.docling_output.strip()

    if not (sentence_transformers or cross_encoders or tiktoken_encodings or docling_output):
        logger.warning("Nothing to download.")
        return 0

    for model_name in sentence_transformers:
        download_sentence_transformer(model_name)
    for model_name in cross_encoders:
        download_cross_encoder(model_name)
    for encoding_name in tiktoken_encodings:
        download_tiktoken_encoding(encoding_name)
    if docling_output:
        download_docling_models(docling_output)

    logger.info("All models are cached.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
