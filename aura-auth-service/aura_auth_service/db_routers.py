"""Router que manda notifications, documents y chat a aura_db; el resto a auth_db."""


class AuraDbRouter:

    _aura_apps = {'notifications', 'documents', 'chat'}

    _aura_account_models: set[str] = set()

    _aura_tables: set[str] = set()

    def _is_aura_db(self, model):
        app = model._meta.app_label
        if app in self._aura_apps:
            return True
        if app == 'accounts' and model._meta.model_name in self._aura_account_models:
            return True
        if model._meta.db_table in self._aura_tables:
            return True
        return False

    def db_for_read(self, model, **hints):
        if self._is_aura_db(model):
            return 'aura_db'
        return None

    def db_for_write(self, model, **hints):
        if self._is_aura_db(model):
            return 'aura_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Nunca migrar sobre aura_db, su esquema lo crea init.sql
        if db == 'aura_db':
            return False
        return None
