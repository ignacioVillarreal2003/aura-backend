"""Serializers de los endpoints de la API de autenticacion."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=255)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.UUIDField()


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.UUIDField()


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.UUIDField()
    token_type = serializers.CharField(default='Bearer')


class ValidateResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    name = serializers.CharField(allow_null=True, required=False)
    roles = serializers.ListField(child=serializers.CharField())
    permissions = serializers.ListField(child=serializers.CharField())


class UserDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    name = serializers.CharField(allow_null=True, required=False)
    email = serializers.EmailField()


class UserListResponseSerializer(serializers.Serializer):
    results = UserDetailSerializer(many=True)
    count = serializers.IntegerField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=255)
    new_password = serializers.CharField(max_length=255, min_length=8)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'La nueva contraseña debe ser diferente a la actual.'}
            )
        return attrs


class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class LogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
