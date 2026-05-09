import logging
import os
import tempfile
import threading
from django.conf import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            model_size = getattr(settings, "WHISPER_MODEL_SIZE", "small")
            device = getattr(settings, "WHISPER_DEVICE", "cuda")
            compute_type = getattr(settings, "WHISPER_COMPUTE_TYPE", "float16")
            logger.info(
                "Loading Whisper model.",
                extra={"model": model_size, "device": device, "compute_type": compute_type},
            )
            _model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Whisper model ready.")
    return _model


class TranscriptionClient:
    def transcribe(self, audio_file) -> str:
        suffix = os.path.splitext(getattr(audio_file, "name", ".wav"))[1] or ".wav"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            model = _get_model()
            segments, info = model.transcribe(tmp_path, beam_size=5)
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            logger.debug(
                "Transcription done.",
                extra={"language": info.language, "length": len(transcript)},
            )
            return transcript
        except Exception as e:
            logger.error("Transcription failed: %s", e, exc_info=True)
            raise
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


transcription_client = TranscriptionClient()
