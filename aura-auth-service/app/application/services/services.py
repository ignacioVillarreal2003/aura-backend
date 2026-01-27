from django.contrib.auth.hashers import make_password
from django.utils import timezone
import logging
import sys
import os

# Add the parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from infrastructure.persistence.repositories.repositories import (
    UserRepository, RoleRepository, UserRoleRepository
)
from domain.models.models import AuthUser, Role, AuthUserInRole

logger = logging.getLogger(__name__)


class UserService:
    """
    Service for user business logic.
    Orchestrates user operations and handles business logic.
    """

    @staticmethod
    def create_user(username: str, email: str, password: str, created_by_id: int) -> AuthUser:
        """
        Creates a new user in the system.
        
        Args:
            username: Username
            email: Email address
            password: Password in plain text
            created_by_id: ID of the user creating this user
            
        Returns:
            AuthUser: The created user
            
        Logic:
            - Hashes the password
            - Automatically sets fields:
              - status = active
              - enabled = true
              - account_non_expired = true
              - account_non_locked = true
              - credentials_non_expired = true
              - failed_login_attempts = 0
              - created_at = now()
        """
        # Hash password
        password_hash = make_password(password)

        msg = "Creating user: {0} ({1})".format(username, email)
        logger.info(msg)

        user = UserRepository.create(
            username=username,
            email=email,
            password_hash=password_hash,
            created_by_id=created_by_id
        )

        msg = "User created successfully: {0}".format(user.id)
        logger.info(msg)
        return user

    @staticmethod
    def get_user(user_id: int) -> AuthUser:
        """Gets a user by ID."""
        return UserRepository.get_by_id(user_id)

    @staticmethod
    def get_all_users():
        """Gets all users."""
        return UserRepository.get_all()

    @staticmethod
    def update_user(user_id: int, updated_by_id: int, **kwargs) -> AuthUser:
        """
        Updates a user.
        
        Args:
            user_id: ID of the user to update
            updated_by_id: ID of the user updating
            **kwargs: Fields to update
            
        Returns:
            AuthUser: The updated user
        """
        kwargs['updated_by_id'] = updated_by_id
        kwargs['updated_at'] = timezone.now()

        if 'password' in kwargs:
            kwargs['password'] = make_password(kwargs['password'])
            kwargs['last_password_change'] = timezone.now()

        msg = "Updating user: {0}".format(user_id)
        logger.info(msg)
        return UserRepository.update(user_id, **kwargs)


class RoleService:
    """
    Service for role business logic.
    """

    @staticmethod
    def create_role(name: str, description: str) -> Role:
        """
        Creates a new role.
        
        Args:
            name: Role name
            description: Role description
            
        Returns:
            Role: The created role
        """
        msg = "Creating role: {0}".format(name)
        logger.info(msg)
        role = RoleRepository.create(name=name, description=description)
        msg = "Role created successfully: {0}".format(role.id)
        logger.info(msg)
        return role

    @staticmethod
    def get_role(role_id: int) -> Role:
        """Gets a role by ID."""
        return RoleRepository.get_by_id(role_id)

    @staticmethod
    def get_all_roles():
        """Gets all roles."""
        return RoleRepository.get_all()

    @staticmethod
    def update_role(role_id: int, **kwargs) -> Role:
        """
        Updates a role.
        
        Args:
            role_id: ID of the role to update
            **kwargs: Fields to update
            
        Returns:
            Role: The updated role
        """
        msg = "Updating role: {0}".format(role_id)
        logger.info(msg)
        return RoleRepository.update(role_id, **kwargs)


class UserRoleService:
    """
    Service for user role assignment business logic.
    """

    @staticmethod
    def assign_role_to_user(user_id: int, role_id: int, created_by_id: int) -> AuthUserInRole:
        """
        Assigns a role to a user.
        
        Args:
            user_id: User ID
            role_id: Role ID
            created_by_id: ID of the user performing the assignment
            
        Returns:
            AuthUserInRole: The created assignment
        """
        msg = "Assigning role {0} to user {1}".format(role_id, user_id)
        logger.info(msg)
        assignment = UserRoleRepository.assign_role(user_id, role_id, created_by_id)
        msg = "Role assigned successfully: {0}".format(assignment.id)
        logger.info(msg)
        return assignment

    @staticmethod
    def get_user_roles(user_id: int):
        """Gets the roles of a user."""
        return UserRoleRepository.get_user_roles(user_id)

    @staticmethod
    def remove_role_from_user(user_id: int, role_id: int, deleted_by_id: int) -> AuthUserInRole:
        """
        Removes (soft delete) the assignment of a role to a user.
        
        Args:
            user_id: User ID
            role_id: Role ID
            deleted_by_id: ID of the user performing the removal
            
        Returns:
            AuthUserInRole: The updated assignment
        """
        msg = "Removing role {0} from user {1}".format(role_id, user_id)
        logger.info(msg)
        assignment = UserRoleRepository.remove_role(user_id, role_id, deleted_by_id)
        logger.info("Role removed successfully")
        return assignment
