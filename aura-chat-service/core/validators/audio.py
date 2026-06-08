from django.conf import settings

SUPPORTED_AUDIO_TYPES: frozenset[str] = frozenset({
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
})
MAX_AUDIO_MB: int = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))
