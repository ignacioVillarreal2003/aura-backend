"""Comando check_schema: verifica que las columnas de los modelos managed=False
existan en la base, para detectar diferencias con el esquema de init.sql."""
import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connections, router


class Command(BaseCommand):
    help = "Verifica que los modelos managed=False coincidan con sus tablas."

    def handle(self, *args, **options):
        errors = 0
        checked = 0

        for model in apps.get_models():
            if model._meta.managed:
                continue
            checked += 1

            table = model._meta.db_table
            alias = router.db_for_read(model) or 'default'
            label = f'{model._meta.label} ({alias}.{table})'

            model_cols = {f.column for f in model._meta.local_concrete_fields}
            db_cols = self._db_columns(alias, table)

            if db_cols is None:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  ✗ {label}: tabla no encontrada'))
                continue

            missing = model_cols - db_cols
            if missing:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ {label}: columnas del modelo ausentes en la BD: {sorted(missing)}'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {label}'))

            extra = db_cols - model_cols
            if extra:
                self.stdout.write(
                    f'      (info) columnas en la BD no mapeadas en el modelo: {sorted(extra)}'
                )

        self.stdout.write('')
        summary = f'Modelos chequeados: {checked} | con errores: {errors}'
        if errors:
            self.stdout.write(self.style.ERROR(summary))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _db_columns(alias, table):
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s",
                    [table],
                )
                rows = cursor.fetchall()
        except Exception:
            return None
        return {r[0] for r in rows} if rows else None
