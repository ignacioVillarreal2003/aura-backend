"""
Django Admin customization for document models.
"""
import requests
from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from .models import Document, DocumentRole


def _apply_audit_fields(obj, username: str, is_create: bool):
    if is_create and not obj.created_by:
        obj.created_by = username
    obj.updated_by = username


class DocumentUploadForm(forms.ModelForm):
    direccion = forms.CharField(
        label='Direccion',
        required=True,
    )
    chat_id = forms.IntegerField(
        label='Chat ID',
        required=True,
    )
    raw_collection = forms.FileField(
        label='Documento',
        required=True,
    )

    class Meta:
        model = Document
        fields = ('name', 'direccion', 'chat_id', 'raw_collection')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin for Document model.
    """
    list_display = (
        'name',
        'size_display',
        'modified_date',
        'created_at',
        'is_deleted_badge',
    )
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'size_bytes'),
        }),
        ('Información de Auditoría', {
            'fields': (
                'created_at',
                'created_by',
                'updated_at',
                'updated_by',
                'deleted_at',
                'deleted_by',
            ),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Información Básica', {
                    'fields': ('name', 'direccion', 'chat_id', 'raw_collection'),
                }),
            )
        return self.fieldsets

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = DocumentUploadForm
        return super().get_form(request, obj, **kwargs)

    def size_display(self, obj):
        if obj.size_bytes is None:
            return '-'
        size = float(obj.size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    size_display.short_description = 'Tamaño'
    size_display.admin_order_field = 'size_bytes'

    def modified_date(self, obj):
        if obj.updated_at:
            return obj.updated_at.strftime('%d/%m/%Y')
        return '-'
    modified_date.short_description = 'Modificado'
    modified_date.admin_order_field = 'updated_at'

    def is_deleted_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Estado'

    def save_model(self, request, obj, form, change):
        if change:
            _apply_audit_fields(obj, request.user.username, is_create=False)
            super().save_model(request, obj, form, change)
            return

        direccion = form.cleaned_data.get('direccion')
        chat_id = form.cleaned_data.get('chat_id')
        raw_collection = form.cleaned_data.get('raw_collection')
        if not raw_collection:
            raise ValidationError('Debe seleccionar un documento.')
        if chat_id is None:
            raise ValidationError('Chat ID es obligatorio.')

        files = {
            'raw_document': (
                raw_collection.name,
                raw_collection,
                raw_collection.content_type or 'application/octet-stream',
            ),
            'raw_collection': (
                raw_collection.name,
                raw_collection,
                raw_collection.content_type or 'application/octet-stream',
            ),
        }
        data = {
            'chat_id': str(chat_id),
        }

        response = requests.post(
            settings.DOCUMENT_PROCESSING_URL,
            files=files,
            data=data,
            timeout=60,
        )
        if not response.ok:
            raise ValidationError(
                f'Error al enviar documento: {response.status_code} {response.text}'
            )

        obj.description = direccion
        obj.size_bytes = raw_collection.size or 0
        _apply_audit_fields(obj, request.user.username, is_create=True)
        super().save_model(request, obj, form, change)


@admin.register(DocumentRole)
class DocumentRoleAdmin(admin.ModelAdmin):
    """
    Admin for DocumentRole relationship.
    """
    list_display = ('document', 'role', 'assigned_at', 'assigned_by')
    list_filter = ('role', 'assigned_at')
    search_fields = ('document__name', 'role__name')
    readonly_fields = ('id', 'assigned_at', 'assigned_by')

    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'document', 'role'),
        }),
        ('Metadatos', {
            'fields': ('assigned_at', 'assigned_by'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.assigned_by:
            obj.assigned_by = request.user.username
        super().save_model(request, obj, form, change)
