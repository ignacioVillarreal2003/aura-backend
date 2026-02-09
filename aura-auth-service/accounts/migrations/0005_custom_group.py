"""
Create custom group model and user-group relation.
"""
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
        ('accounts', '0004_user_is_super_admin_refreshtoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomGroup',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Creation timestamp', verbose_name='Creado')),
                ('created_by', models.CharField(blank=True, help_text='Username who created this record', max_length=255, null=True, verbose_name='Creado por')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Last update timestamp', verbose_name='Actualizado el')),
                ('updated_by', models.CharField(blank=True, help_text='Username who last updated this record', max_length=255, null=True, verbose_name='Actualizado por')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='Soft delete timestamp (null = active)', null=True, verbose_name='Eliminado el')),
                ('deleted_by', models.CharField(blank=True, help_text='Username who deleted this record', max_length=255, null=True, verbose_name='Eliminado por')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, max_length=150, unique=True, verbose_name='Nombre')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('documents', models.ManyToManyField(blank=True, related_name='groups', to='documents.document', verbose_name='Documentos')),
            ],
            options={
                'verbose_name': 'Grupo',
                'verbose_name_plural': 'Grupos',
                'db_table': 'custom_groups',
            },
        ),
        migrations.AddField(
            model_name='user',
            name='custom_groups',
            field=models.ManyToManyField(blank=True, related_name='users', to='accounts.customgroup', verbose_name='Grupos'),
        ),
        migrations.AddIndex(
            model_name='customgroup',
            index=models.Index(fields=['name'], name='custom_gro_name_8c5f90_idx'),
        ),
        migrations.AddIndex(
            model_name='customgroup',
            index=models.Index(fields=['deleted_at'], name='custom_gro_deleted_2b06a5_idx'),
        ),
    ]
