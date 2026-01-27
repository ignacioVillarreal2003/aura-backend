from django.db import IntegrityError
import sys
import os

# Add the parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from domain.models.models import AuthUser, Role, AuthUserInRole, Permission
from application.exceptions.exceptions import (
    UserNotFoundException, RoleNotFoundException,
    RoleAlreadyAssignedException, IntegrityException
)


class UserRepository:
    """
    Repository for user persistence operations.
    """

    @staticmethod
    def create(username: str, email: str, password_hash: str, created_by_id: int) -> AuthUser:
        """
        Creates a new user.
        
        Args:
            username: Username
            email: Email address
            password_hash: Hashed password
            created_by_id: ID of the user creating this user
            
        Returns:
            AuthUser: The created user
            
        Raises:
            IntegrityException: If there is an integrity error
        """
        try:
            user = AuthUser.objects.create(
                username=username,
                email=email,
                password=password_hash,
                status='active',
                enabled=True,
                account_non_expired=True,
                account_non_locked=True,
                credentials_non_expired=True,
                failed_login_attempts=0,
                created_by_id=created_by_id
            )
            return user
        except IntegrityError as e:
            error_msg = "Integrity error: {0}".format(str(e))
            raise IntegrityException(detail=error_msg)

    @staticmethod
    def get_by_id(user_id: int) -> AuthUser:
        """
        Gets a user by ID.
        
        Raises:
            UserNotFoundException: If the user does not exist
        """
        try:
            return AuthUser.objects.get(id=user_id)
        except AuthUser.DoesNotExist:
            raise UserNotFoundException()

    @staticmethod
    def get_by_username(username: str) -> AuthUser:
        """Gets a user by username."""
        try:
            return AuthUser.objects.get(username=username)
        except AuthUser.DoesNotExist:
            raise UserNotFoundException()

    @staticmethod
    def get_all():
        """Gets all users."""
        return AuthUser.objects.all().order_by('-created_at')

    @staticmethod
    def update(user_id: int, **kwargs) -> AuthUser:
        """
        Updates a user.
        
        Raises:
            UserNotFoundException: If the user does not exist
        """
        user = UserRepository.get_by_id(user_id)
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        user.save()
        return user


class RoleRepository:
    """
    Repository for role persistence operations.
    """

    @staticmethod
    def create(name: str, description: str) -> Role:
        """
        Creates a new role.
        
        Raises:
            IntegrityException: If the role already exists
        """
        try:
            return Role.objects.create(name=name, description=description)
        except IntegrityError as e:
            error_msg = "Integrity error: {0}".format(str(e))
            raise IntegrityException(detail=error_msg)

    @staticmethod
    def get_by_id(role_id: int) -> Role:
        """
        Gets a role by ID.
        
        Raises:
            RoleNotFoundException: If the role does not exist
        """
        try:
            return Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            raise RoleNotFoundException()

    @staticmethod
    def get_all():
        """Gets all roles."""
        return Role.objects.all().order_by('name')

    @staticmethod
    def update(role_id: int, **kwargs) -> Role:
        """
        Updates a role.
        
        Raises:
            RoleNotFoundException: If the role does not exist
        """
        role = RoleRepository.get_by_id(role_id)
        for key, value in kwargs.items():
            if hasattr(role, key):
                setattr(role, key, value)
        role.save()
        return role


class UserRoleRepository:
    """
    Repository for user role assignment operations.
    """

    @staticmethod
    def assign_role(user_id: int, role_id: int, created_by_id: int) -> AuthUserInRole:
        """
        Assigns a role to a user.
        
        Raises:
            UserNotFoundException: If the user does not exist
            RoleNotFoundException: If the role does not exist
            RoleAlreadyAssignedException: If the role is already assigned
            IntegrityException: If there is an integrity error
        """
        # Validate that user and role exist
        user = UserRepository.get_by_id(user_id)
        role = RoleRepository.get_by_id(role_id)

        # Check that it is not already assigned
        existing = AuthUserInRole.objects.filter(
            auth_user_id=user_id,
            role_id=role_id,
            deleted_at__isnull=True
        ).first()

        if existing:
            raise RoleAlreadyAssignedException()

        try:
            return AuthUserInRole.objects.create(
                auth_user_id=user_id,
                role_id=role_id,
                created_by_id=created_by_id
            )
        except IntegrityError as e:
            error_msg = "Integrity error: {0}".format(str(e))
            raise IntegrityException(detail=error_msg)

    @staticmethod
    def get_user_roles(user_id: int):
        """Gets the active roles of a user."""
        return AuthUserInRole.objects.filter(
            auth_user_id=user_id,
            deleted_at__isnull=True
        ).select_related('role')

    @staticmethod
    def remove_role(user_id: int, role_id: int, deleted_by_id: int):
        """
        Removes (soft delete) the assignment of a role to a user.
        """
        from django.utils import timezone
        
        try:
            assignment = AuthUserInRole.objects.get(
                auth_user_id=user_id,
                role_id=role_id,
                deleted_at__isnull=True
            )
            assignment.deleted_at = timezone.now()
            assignment.deleted_by_id = deleted_by_id
            assignment.save()
            return assignment
        except AuthUserInRole.DoesNotExist:
            raise RoleNotFoundException()
