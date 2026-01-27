from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
import logging
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from domain.models.models import AuthUser, Role, AuthUserInRole
from domain.dtos.serializers import (
    UserCreateRequestSerializer, UserResponseSerializer, UserListResponseSerializer,
    RoleCreateRequestSerializer, RoleResponseSerializer, RoleListResponseSerializer,
    UserRoleAssignmentRequestSerializer, UserRoleAssignmentResponseSerializer,
    PermissionResponseSerializer
)
from application.services.services import UserService, RoleService, UserRoleService
from application.exceptions.exceptions import (
    UserNotFoundException, RoleNotFoundException, UserAlreadyExistsException
)

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    
    Endpoints:
        POST /admin/users - Create user
        GET /admin/users - List users
        GET /admin/users/{id} - Get user
        POST /admin/users/{id}/roles - Assign role
    """
    queryset = AuthUser.objects.all()
    serializer_class = UserResponseSerializer

    def get_serializer_class(self):
        """Returns the appropriate serializer based on the action."""
        if self.action == 'create':
            return UserCreateRequestSerializer
        elif self.action == 'list':
            return UserListResponseSerializer
        elif self.action == 'assign_role':
            return UserRoleAssignmentRequestSerializer
        return UserResponseSerializer

    def create(self, request: Request):
        """
        Creates a new user.
        
        Body:
            {
                "username": "jdoe",
                "email": "john@example.com",
                "password": "SecurePass123!"
            }
        
        Response (201):
            {
                "success": true,
                "data": {
                    "id": 1,
                    "username": "jdoe",
                    "email": "john@example.com",
                    "status": "active",
                    "enabled": true,
                    "created_at": "2024-01-01T10:00:00Z"
                }
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Get the user creating this user (for audit)
            # In a real system, it would be request.user.id
            # For now, use a hardcoded ID (this will be improved with authentication)
            created_by_id = request.data.get('created_by_id', 1)

            user = UserService.create_user(
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                created_by_id=created_by_id
            )

            response_serializer = UserResponseSerializer(user)
            return Response(
                {
                    'success': True,
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            error_msg = "Error creating user: {0}".format(str(e))
            logger.error(error_msg, exc_info=True)
            raise

    def list(self, request: Request):
        """
        Lists all users.
        
        Response (200):
            {
                "success": true,
                "data": [
                    {
                        "id": 1,
                        "username": "jdoe",
                        "email": "john@example.com",
                        "status": "active",
                        "enabled": true,
                        "roles": [{"id": 1, "name": "admin"}],
                        "created_at": "2024-01-01T10:00:00Z"
                    }
                ]
            }
        """
        try:
            users = UserService.get_all_users()
            serializer = self.get_serializer(users, many=True)
            return Response(
                {
                    'success': True,
                    'data': serializer.data,
                    'count': len(serializer.data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            error_msg = "Error listing users: {0}".format(str(e))
            logger.error(error_msg, exc_info=True)
            raise

    def retrieve(self, request: Request, pk=None):
        """
        Gets a specific user by ID.
        
        Response (200):
            {
                "success": true,
                "data": {
                    "id": 1,
                    "username": "jdoe",
                    "email": "john@example.com",
                    "status": "active",
                    "enabled": true,
                    "created_at": "2024-01-01T10:00:00Z"
                }
            }
        """
        try:
            user = UserService.get_user(pk)
            serializer = UserResponseSerializer(user)
            return Response(
                {
                    'success': True,
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except UserNotFoundException:
            return Response(
                {
                    'success': False,
                    'error': 'User not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def assign_role(self, request: Request, pk=None):
        """
        Assigns a role to a user.
        
        URL: POST /admin/users/{id}/assign_role
        
        Body:
            {
                "role_id": 1
            }
        
        Response (201):
            {
                "success": true,
                "data": {
                    "id": 1,
                    "user": {
                        "id": 1,
                        "username": "jdoe",
                        "email": "john@example.com"
                    },
                    "role": {
                        "id": 1,
                        "name": "admin",
                        "description": "Administrator"
                    },
                    "created_at": "2024-01-01T10:00:00Z"
                }
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            created_by_id = request.data.get('created_by_id', 1)

            assignment = UserRoleService.assign_role_to_user(
                user_id=pk,
                role_id=serializer.validated_data['role_id'],
                created_by_id=created_by_id
            )

            response_serializer = UserRoleAssignmentResponseSerializer(assignment)
            return Response(
                {
                    'success': True,
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            error_msg = "Error assigning role: {0}".format(str(e))
            logger.error(error_msg, exc_info=True)
            raise


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for role management.
    
    Endpoints:
        POST /admin/roles - Create role
        GET /admin/roles - List roles
        GET /admin/roles/{id} - Get role
    """
    queryset = Role.objects.all()
    serializer_class = RoleResponseSerializer

    def get_serializer_class(self):
        """Returns the appropriate serializer based on the action."""
        if self.action == 'create':
            return RoleCreateRequestSerializer
        elif self.action == 'list':
            return RoleListResponseSerializer
        return RoleResponseSerializer

    def create(self, request: Request):
        """
        Creates a new role.
        
        Body:
            {
                "name": "admin",
                "description": "Administrator of the system"
            }
        
        Response (201):
            {
                "success": true,
                "data": {
                    "id": 1,
                    "name": "admin",
                    "description": "Administrator of the system",
                    "permissions": []
                }
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            role = RoleService.create_role(
                name=serializer.validated_data['name'],
                description=serializer.validated_data['description']
            )

            response_serializer = RoleResponseSerializer(role)
            return Response(
                {
                    'success': True,
                    'data': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            error_msg = "Error creating role: {0}".format(str(e))
            logger.error(error_msg, exc_info=True)
            raise

    def list(self, request: Request):
        """
        Lists all roles.
        
        Response (200):
            {
                "success": true,
                "data": [
                    {
                        "id": 1,
                        "name": "admin",
                        "description": "Administrator of the system"
                    }
                ]
            }
        """
        try:
            roles = RoleService.get_all_roles()
            serializer = self.get_serializer(roles, many=True)
            return Response(
                {
                    'success': True,
                    'data': serializer.data,
                    'count': len(serializer.data)
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            error_msg = "Error listing roles: {0}".format(str(e))
            logger.error(error_msg, exc_info=True)
            raise

    def retrieve(self, request: Request, pk=None):
        """
        Gets a specific role by ID.
        
        Response (200):
            {
                "success": true,
                "data": {
                    "id": 1,
                    "name": "admin",
                    "description": "Administrator of the system",
                    "permissions": []
                }
            }
        """
        try:
            role = RoleService.get_role(pk)
            serializer = RoleResponseSerializer(role)
            return Response(
                {
                    'success': True,
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except RoleNotFoundException:
            return Response(
                {
                    'success': False,
                    'error': 'Role not found'
                },
                status=status.HTTP_404_NOT_FOUND
            )
