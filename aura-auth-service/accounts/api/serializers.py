"""Serializers for auth API endpoints."""

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.UUIDField()


class IntrospectSerializer(serializers.Serializer):
    token = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.UUIDField()
