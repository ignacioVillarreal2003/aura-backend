from rest_framework import serializers


class SendMessageRequest(serializers.Serializer):
    message = serializers.CharField(max_length=10000)
