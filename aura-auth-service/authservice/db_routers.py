"""
Database router for aura-auth-service.

Routes the 'notifications' app to aura_db.
All other apps continue using the default (auth_db).
"""


class AuraDbRouter:
    """Route notifications app models to aura_db."""

    _aura_apps = {'notifications'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self._aura_apps:
            return 'aura_db'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self._aura_apps:
            return 'aura_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations within the same database
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # aura-notification-service owns migrations for these tables
        if app_label in self._aura_apps:
            return False
        return None
