from apps.artifact.exceptions import TranscriptionBusyException, TranscriptionException
from core.clients.transcription_client import TranscriptionBusyError, transcription_client


def transcribe(audio_file) -> str:
    try:
        return transcription_client.transcribe(audio_file)
    except TranscriptionBusyError as exc:
        raise TranscriptionBusyException() from exc
    except Exception as exc:
        raise TranscriptionException() from exc
