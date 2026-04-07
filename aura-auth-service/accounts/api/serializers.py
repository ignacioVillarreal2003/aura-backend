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


# Response serializers
class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.UUIDField()
    token_type = serializers.CharField(default='Bearer')


class IntrospectResponseSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    roles = serializers.ListField(child=serializers.CharField())
    permissions = serializers.ListField(child=serializers.CharField())
    is_super_admin = serializers.BooleanField()


class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class LogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class MeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    roles = serializers.ListField(child=serializers.CharField())
    permissions = serializers.ListField(child=serializers.CharField())
