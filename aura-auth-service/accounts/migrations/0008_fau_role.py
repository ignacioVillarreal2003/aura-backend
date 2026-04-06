"""Create FauRole model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_user_enabled'),
    ]

    operations = [
        migrations.CreateModel(
            name='FauRole',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Nombre')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Descripción')),
            ],
            options={
                'verbose_name': 'Rol FAU',
                'verbose_name_plural': 'Rol FAU',
                'db_table': 'fau_role',
            },
        ),
    ]
