from rest_framework import serializers


class CreateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    system_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    response_style = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class UpdateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    response_style = serializers.CharField(required=False, allow_blank=True, allow_null=True)
