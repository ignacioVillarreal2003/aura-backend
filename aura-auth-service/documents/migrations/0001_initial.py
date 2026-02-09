"""
Initial migration for documents app.
"""
import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0004_user_is_super_admin_refreshtoken'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Creation timestamp', verbose_name='Creado')),
                ('created_by', models.CharField(blank=True, help_text='Username who created this record', max_length=255, null=True, verbose_name='Creado por')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Last update timestamp', verbose_name='Actualizado el')),
                ('updated_by', models.CharField(blank=True, help_text='Username who last updated this record', max_length=255, null=True, verbose_name='Actualizado por')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='Soft delete timestamp (null = active)', null=True, verbose_name='Eliminado el')),
                ('deleted_by', models.CharField(blank=True, help_text='Username who deleted this record', max_length=255, null=True, verbose_name='Eliminado por')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, help_text='Nombre del documento', max_length=255, verbose_name='Nombre')),
                ('description', models.TextField(blank=True, help_text='Descripción opcional', verbose_name='Descripción')),
                ('size_bytes', models.PositiveBigIntegerField(default=0, help_text='Tamaño del archivo en bytes', verbose_name='Tamaño (bytes)')),
            ],
            options={
                'verbose_name': 'Documento',
                'verbose_name_plural': 'Documentos',
                'db_table': 'documents',
            },
        ),
        migrations.CreateModel(
            name='DocumentRole',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('assigned_at', models.DateTimeField(auto_now_add=True, verbose_name='Asignado el')),
                ('assigned_by', models.CharField(blank=True, max_length=255, null=True, verbose_name='Asignado por')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_assignments', to='documents.document', verbose_name='Documento')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_assignments', to='accounts.role', verbose_name='Rol')),
            ],
            options={
                'verbose_name': 'Documento por Rol',
                'verbose_name_plural': 'Documentos por Rol',
                'db_table': 'document_roles',
                'unique_together': {('document', 'role')},
            },
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['name'], name='documents_name_7e31f9_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['deleted_at'], name='documents_deleted_4df53c_idx'),
        ),
        migrations.AddIndex(
            model_name='documentrole',
            index=models.Index(fields=['document'], name='document_ro_document_50d0b6_idx'),
        ),
        migrations.AddIndex(
            model_name='documentrole',
            index=models.Index(fields=['role'], name='document_ro_role_id_4a3c85_idx'),
        ),
    ]
