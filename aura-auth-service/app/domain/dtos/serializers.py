from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.utils import timezone
import sys
import os

# Agregar el directorio app al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from domain.models.models import AuthUser, Role, AuthUserInRole, Permission, PermissionInRole


class UserCreateRequestSerializer(serializers.Serializer):
    """
    Serializer for creating a user.
    Validates and formats input data.
    """
    username = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Unique username"
    )
    email = serializers.EmailField(
        required=True,
        help_text="Unique email address"
    )
    password = serializers.CharField(
        max_length=255,
        required=True,
        write_only=True,
        help_text="Password (minimum 8 characters)"
    )

    def validate_password(self, value):
        """Validates that the password has a minimum of 8 characters."""
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must have at least 8 characters."
            )
        return value

    def validate_username(self, value):
        """Validates that the username does not exist."""
        if AuthUser.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already in use."
            )
        return value

    def validate_email(self, value):
        """Validates that the email does not exist."""
        if AuthUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value


class UserResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for user responses.
    Includes public fields of the user.
    """
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = AuthUser
        fields = [
            'id', 'username', 'email', 'status', 'status_display',
            'enabled', 'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_status_display(self, obj):
        """Returns the descriptive name of the status."""
        return obj.get_status_display()


class UserListResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for listing users with reduced information.
    """
    status_display = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = AuthUser
        fields = [
            'id', 'username', 'email', 'status', 'status_display',
            'enabled', 'roles', 'created_at'
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_roles(self, obj):
        """Gets the roles assigned to the user."""
        roles = obj.user_roles.filter(deleted_at__isnull=True)
        return [
            {'id': role.role.id, 'name': role.role.name}
            for role in roles
        ]


class RoleCreateRequestSerializer(serializers.Serializer):
    """
    Serializer for creating a role.
    """
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Unique name for the role"
    )
    description = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Description of the role"
    )

    def validate_name(self, value):
        """Validates that the role name does not exist."""
        if Role.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                "This role name is already in use."
            )
        return value


class RoleResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for role responses.
    """
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'permissions']

    def get_permissions(self, obj):
        """Gets the permissions assigned to the role."""
        perms = obj.role_permissions.all()
        return [
            {'id': perm.permission.id, 'name': perm.permission.name}
            for perm in perms
        ]


class RoleListResponseSerializer(serializers.ModelSerializer):
    """
    Serializer para listar roles.
    """
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']


class UserRoleAssignmentRequestSerializer(serializers.Serializer):
    """
    Serializer for assigning a role to a user.
    """
    role_id = serializers.IntegerField(
        required=True,
        help_text="ID of the role to assign"
    )

    def validate_role_id(self, value):
        """Validates that the role exists."""
        if not Role.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "The specified role does not exist."
            )
        return value


class UserRoleAssignmentResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for role assignment responses.
    """
    role = RoleListResponseSerializer(read_only=True)
    user = UserResponseSerializer(source='auth_user', read_only=True)

    class Meta:
        model = AuthUserInRole
        fields = ['id', 'user', 'role', 'created_at']


class PermissionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for permission responses.
    """
    class Meta:
        model = Permission
        fields = ['id', 'name', 'description']
