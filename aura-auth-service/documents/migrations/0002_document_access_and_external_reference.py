"""Add document access control and external reference fields."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_faurole_power_user_faurole_permissioninfaurole'),
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='external_document_id',
            field=models.BigIntegerField(
                blank=True,
                help_text='Identificador del documento en document-processing.',
                null=True,
                unique=True,
                verbose_name='ID externo',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='external_storage_url',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Referencia devuelta por document-processing.',
                max_length=1000,
                verbose_name='Storage URL externa',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='document',
            name='minimum_fau_role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='document_minimum_access',
                to='accounts.faurole',
                verbose_name='Rol FAU mínimo',
                help_text='Este rol y cualquier rol con mayor poder pueden acceder al documento.',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='visible_to_all',
            field=models.BooleanField(
                default=False,
                help_text='Si está activo, el documento queda disponible para todos y no se restringe por grupos ni jerarquía FAU.',
                verbose_name='Disponible para todos',
            ),
        ),
    ]