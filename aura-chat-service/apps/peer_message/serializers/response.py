from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.peer_message.models import PeerMessage


class PeerMessageResponse(serializers.ModelSerializer):
    is_edited = serializers.SerializerMethodField()

    class Meta:
        model = PeerMessage
        fields = [
            "id",
            "chat_id",
            "message",
            "created_by",
            "created_at",
            "updated_at",
            "is_edited",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_edited(self, obj) -> bool:
        return getattr(obj, "updated_at", None) is not None
