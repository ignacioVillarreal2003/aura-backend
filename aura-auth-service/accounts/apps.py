"""
AppConfig for accounts application.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Configuration for the accounts application.
    
    This app manages:
    - User model with custom authentication
    - Role-based access control (RBAC)
    - Permissions management
    - User-Role and Role-Permission relationships
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Gestión de Usuarios'
