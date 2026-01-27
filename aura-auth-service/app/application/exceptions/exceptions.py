from rest_framework.exceptions import APIException
from rest_framework import status


class BaseApplicationException(APIException):
    """
    Base exception for all application exceptions.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'Internal server error.'
    default_code = 'internal_error'


class UserAlreadyExistsException(APIException):
    """Exception raised when attempting to create a user that already exists."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'User already exists.'
    default_code = 'user_already_exists'


class UserNotFoundException(APIException):
    """Exception raised when a user is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'User not found.'
    default_code = 'user_not_found'


class RoleNotFoundException(APIException):
    """Exception raised when a role is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Role not found.'
    default_code = 'role_not_found'


class RoleAlreadyExistsException(APIException):
    """Exception raised when attempting to create a role that already exists."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Role already exists.'
    default_code = 'role_already_exists'


class RoleAlreadyAssignedException(APIException):
    """Exception raised when attempting to assign a role that is already assigned."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'User already has this role assigned.'
    default_code = 'role_already_assigned'


class InvalidPasswordException(APIException):
    """Exception raised when a password does not meet requirements."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Password does not meet security requirements.'
    default_code = 'invalid_password'


class IntegrityException(APIException):
    """Exception raised when there is a database integrity error."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Database integrity error.'
    default_code = 'integrity_error'
