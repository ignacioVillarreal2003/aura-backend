"""
Database router for aura-auth-service.

Routing rules:
  - notifications app           → aura_db  (all models)
  - documents app               → aura_db  (all models)
  - accounts.CustomGroup        → aura_db  (single model within accounts app)
  - implicit M2M through tables → aura_db  (identified by db_table name)
  - everything else             → auth_db  (Django default)

aura_db schema is owned by docker/aura-db/init.sql — no Django migrations run there.
auth_db schema is owned by docker/auth-db/init.sql — same rule for local apps.
"""


class AuraDbRouter:

    # Apps where every model lives in aura_db.
    _aura_apps = {'notifications', 'documents', 'chat'}

    # Individual model names (lowercase) inside the accounts app that live in aura_db.
    _aura_account_models = {'customgroup'}

    # db_table names that always route to aura_db.
    # Used for implicit M2M through-tables whose app_label inherits from the
    # source model (accounts) but whose physical table is in aura_db.
    _aura_tables = {'auth_user_custom_groups', 'custom_groups_documents'}

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
        # Allow all relations — cross-DB FKs are converted to plain BigInt in
        # the models, so no SQL-level FK constraints exist across databases.
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never run any Django migrations against aura_db — its schema is
        # owned exclusively by docker/aura-db/init.sql.
        if db == 'aura_db':
            return False
        # Local app tables (accounts, documents, notifications) are also
        # owned by init.sql, blocked via MIGRATION_MODULES=None in settings.
        return None
