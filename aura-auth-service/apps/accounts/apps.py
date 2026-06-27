"""AppConfig de la app accounts."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """App de usuarios, roles y permisos."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Gestión de Usuarios'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        from apps.accounts.services.elevation_service import close_stale_elevation
        from apps.accounts.ldap_sync import connect_signals

        def _on_user_login(sender, request, user, **kwargs):
            close_stale_elevation(user)

        user_logged_in.connect(_on_user_login, weak=False)
        connect_signals()
