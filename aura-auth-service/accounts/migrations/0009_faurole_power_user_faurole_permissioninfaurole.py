"""Add power to FauRole, fau_role FK to User, PermissionInFauRole model."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_fau_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='faurole',
            name='power',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Número único que define la jerarquía (mayor número = mayor poder).',
                null=True,
                unique=True,
                verbose_name='Nivel de poder',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='fau_role',
            field=models.ForeignKey(
                blank=True,
                db_column='fau_role_id',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users',
                to='accounts.faurole',
                verbose_name='Rol FAU',
            ),
        ),
        migrations.CreateModel(
            name='PermissionInFauRole',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('fau_role', models.ForeignKey(
                    db_column='fau_role_id',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='permission_links',
                    to='accounts.faurole',
                    verbose_name='Rol FAU',
                )),
                ('permission', models.ForeignKey(
                    db_column='permission_id',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='fau_role_links',
                    to='accounts.permission',
                    verbose_name='Permiso',
                )),
            ],
            options={
                'verbose_name': 'Permiso de Rol FAU',
                'verbose_name_plural': 'Permisos de Rol FAU',
                'db_table': 'permission_in_fau_role',
                'unique_together': {('fau_role', 'permission')},
            },
        ),
        migrations.AlterModelOptions(
            name='faurole',
            options={
                'ordering': ['power'],
                'verbose_name': 'Rol FAU',
                'verbose_name_plural': 'Roles FAU',
            },
        ),
    ]
