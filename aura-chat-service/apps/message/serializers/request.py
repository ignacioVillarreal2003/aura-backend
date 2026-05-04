from rest_framework import serializers

_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = 25


class SendMessageRequest(serializers.Serializer):
    message = serializers.CharField(max_length=10000, required=False, allow_blank=False)
    audio = serializers.FileField(required=False)

    def validate_audio(self, file):
        content_type = getattr(file, "content_type", "")
        if content_type not in _SUPPORTED_AUDIO_TYPES:
            raise serializers.ValidationError(
                f"Formato no soportado '{content_type}'. Usar: mp3, mp4, wav, webm, ogg, flac."
            )
        if file.size > _MAX_AUDIO_MB * 1024 * 1024:
            raise serializers.ValidationError(f"El audio no puede superar {_MAX_AUDIO_MB} MB.")
        return file

    def validate(self, attrs):
        has_text = bool(attrs.get("message"))
        has_audio = bool(attrs.get("audio"))
        if not has_text and not has_audio:
            raise serializers.ValidationError("Enviá 'message' (texto) o 'audio' (archivo).")
        if has_text and has_audio:
            raise serializers.ValidationError("Enviá solo uno: 'message' o 'audio'.")
        return attrs
