from rest_framework import serializers

from apps.assistant.models import Assistant

_SYSTEM_PROMPT_MAX = 8000
_RESPONSE_STYLE_MAX = 2000


class CreateAssistantRequest(serializers.Serializer):
    name = serializers.CharField(max_length=256, allow_blank=False)
    description = serializers.CharField(default="", allow_blank=True, required=False)
    system_prompt = serializers.CharField(allow_blank=False, max_length=_SYSTEM_PROMPT_MAX)
    response_style = serializers.CharField(default="", allow_blank=True, required=False, max_length=_RESPONSE_STYLE_MAX)
    avatar_emoji = serializers.CharField(max_length=16, default="", allow_blank=True, required=False)
    is_active = serializers.BooleanField(default=True, required=False)


class UpdateAssistantRequest(serializers.Serializer):
    name = serializers.CharField(max_length=256, allow_blank=False, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    system_prompt = serializers.CharField(allow_blank=False, required=False, max_length=_SYSTEM_PROMPT_MAX)
    response_style = serializers.CharField(default="", allow_blank=True, required=False, max_length=_RESPONSE_STYLE_MAX)
    avatar_emoji = serializers.CharField(max_length=16, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data


class StartChatRequest(serializers.Serializer):
    resume = serializers.BooleanField(default=False, required=False)


class AssistantUserResponse(serializers.ModelSerializer):
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
    class Meta:
        model = Assistant
        fields = [
            "id",
            "name",
            "description",
            "system_prompt",
            "response_style",
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
    is_new = serializers.BooleanField()
