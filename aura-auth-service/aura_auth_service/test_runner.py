"""Test runner que corre init.sql entre crear la base de pruebas y migrar."""

import os
from django.test.runner import DiscoverRunner
from django.db.backends.postgresql.creation import DatabaseCreation

_INIT_SQL = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'docker', 'database', 'auth-db', 'init.sql',
    )
)


class AuthDbCreation(DatabaseCreation):

    def create_test_db(self, verbosity=1, autoclobber=False, serialize=True, keepdb=False):
        import psycopg2
        from django.core.management import call_command
        from django.conf import settings as dj_settings

        test_db_name = self._get_test_db_name()

        if verbosity >= 1:
            self.log(
                'Creating test database for alias %s...'
                % self._get_database_display_str(verbosity, test_db_name)
            )

        if not self.connection.settings_dict['TEST']['MIRROR']:
            self._create_test_db(verbosity, autoclobber, keepdb)
            self.connection.ensure_connection()

            if not keepdb:
                self.connection.close()
                dj_settings.DATABASES[self.connection.alias]['NAME'] = test_db_name
                self.connection.settings_dict['NAME'] = test_db_name

            db = self.connection.settings_dict
            pg_conn = psycopg2.connect(
                dbname=test_db_name,
                user=db['USER'],
                password=db['PASSWORD'],
                host=db['HOST'],
                port=int(db['PORT']),
            )
            try:
                pg_conn.autocommit = True
                with pg_conn.cursor() as cur:
                    with open(_INIT_SQL, encoding='utf-8') as f:
                        cur.execute(f.read())
            finally:
                pg_conn.close()

            call_command(
                'migrate',
                verbosity=max(verbosity - 1, 0),
                interactive=False,
                database=self.connection.alias,
                run_syncdb=True,
            )

        if serialize:
            self.connection._test_serialized_contents = self.serialize_db_to_string()

        call_command('createcachetable', database=self.connection.alias, verbosity=0)

        return test_db_name


class AuthDbTestRunner(DiscoverRunner):

    def setup_databases(self, **kwargs):
        from django.db import connections
        connections['default'].creation.__class__ = AuthDbCreation
        return super().setup_databases(**kwargs)
