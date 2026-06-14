import concurrent.futures as _cf
import logging
import os
import tempfile
import threading
from django.conf import settings

logger = logging.getLogger(__name__)


class TranscriptionBusyError(Exception):
    pass


_model = None
_model_lock = threading.Lock()

_MAX_CONCURRENCY = max(int(getattr(settings, "WHISPER_MAX_CONCURRENCY", 2)), 1)
_slots = threading.BoundedSemaphore(_MAX_CONCURRENCY)
_transcribe_pool = _cf.ThreadPoolExecutor(max_workers=_MAX_CONCURRENCY, thread_name_prefix="whisper")


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            model_size = getattr(settings, "WHISPER_MODEL_SIZE", "small")
            device = getattr(settings, "WHISPER_DEVICE", "cpu")
            compute_type = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
            logger.info(
                "Loading Whisper model.",
                extra={"model": model_size, "device": device, "compute_type": compute_type},
            )
            _model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model ready.")
    return _model


def preload_model_in_background() -> None:
    def _load() -> None:
        try:
            _get_model()
        except Exception:
            logger.exception("Whisper model preload failed; it will be retried on first use.")

    threading.Thread(target=_load, name="whisper-preload", daemon=True).start()


class TranscriptionClient:
    def transcribe(self, audio_file) -> str:
        if not _slots.acquire(blocking=False):
            logger.warning(
                "Transcription rejected: all %d slots busy.", _MAX_CONCURRENCY
            )
            raise TranscriptionBusyError()
        try:
            return self._transcribe(audio_file)
        finally:
            _slots.release()

    @staticmethod
    def _transcribe(audio_file) -> str:
        suffix = os.path.splitext(getattr(audio_file, "name", ".wav"))[1] or ".wav"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                for chunk in audio_file.chunks():
                    f.write(chunk)

            model = _get_model()
            timeout = getattr(settings, "WHISPER_TIMEOUT_SECONDS", 120)
            future = _transcribe_pool.submit(model.transcribe, tmp_path, beam_size=5)
            try:
                segments, info = future.result(timeout=timeout)
            except _cf.TimeoutError:
                logger.error("Transcription timed out after %ss.", timeout)
                raise

            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            logger.debug(
                "Transcription done.",
                extra={"language": info.language, "length": len(transcript)},
            )
            return transcript
        except Exception as e:
            if not isinstance(e, _cf.TimeoutError):
                logger.error("Transcription failed: %s", e, exc_info=True)
            raise
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


transcription_client = TranscriptionClient()
