from rest_framework import serializers

from apps.assistant.models import Assistant


class CreateAssistantRequest(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=False)
    description = serializers.CharField(default="", allow_blank=True)
    system_prompt = serializers.CharField(allow_blank=False)
    avatar_emoji = serializers.CharField(max_length=10, default="", allow_blank=True)
    is_active = serializers.BooleanField(default=True)


class UpdateAssistantRequest(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=False, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    system_prompt = serializers.CharField(allow_blank=False, required=False)
    avatar_emoji = serializers.CharField(max_length=10, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class AssistantUserResponse(serializers.ModelSerializer):
    """Response for regular users — system_prompt is not exposed."""

    class Meta:
        model = Assistant
        fields = [
            "id",
            "name",
            "description",
            "avatar_emoji",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class AssistantAdminResponse(serializers.ModelSerializer):
    """Response for admins — includes system_prompt."""

    class Meta:
        model = Assistant
        fields = [
            "id",
            "name",
            "description",
            "system_prompt",
            "avatar_emoji",
            "is_active",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class StartChatResponse(serializers.Serializer):
    chat_id = serializers.IntegerField()
    chat_name = serializers.CharField()
