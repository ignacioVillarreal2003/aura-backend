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

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        from accounts.services.elevation_service import close_stale_elevation
        from accounts.ldap_sync import connect_signals

        def _on_user_login(sender, request, user, **kwargs):
            close_stale_elevation(user)

        user_logged_in.connect(_on_user_login, weak=False)
        connect_signals()
