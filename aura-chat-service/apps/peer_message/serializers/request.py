from rest_framework import serializers

_MESSAGE_MAX = 10000


class _PeerMessageBody(serializers.Serializer):
    message = serializers.CharField(
        max_length=_MESSAGE_MAX,
        trim_whitespace=True,
        help_text="Message body (max 10000 characters).",
    )

    def validate_message(self, value: str) -> str:
        text = value.strip()
        if not text:
            raise serializers.ValidationError("Message cannot be empty.")
        return text


class CreatePeerMessageRequest(_PeerMessageBody):
    pass


class UpdatePeerMessageRequest(_PeerMessageBody):
    pass
