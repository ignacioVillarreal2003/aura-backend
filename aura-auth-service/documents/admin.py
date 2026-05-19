"""Django Admin for Document model — groups replaced by MAC document collections."""

from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.contrib.admin.utils import flatten_fieldsets, unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, router, transaction
from django.forms.formsets import all_valid
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django.conf import settings

from accounts.admin_parts.utils.audit import log_audit
from documents.models import Document
from documents.services.document_processing_client import (
    DocumentProcessingServiceError,
    create_document_from_admin,
)
def _apply_audit_fields(obj, user_id: int, is_create: bool):
    if is_create and not obj.created_by:
        obj.created_by = user_id
    obj.updated_by = user_id


def _ensure_admin_chat(actor_user_id: int) -> int:
    admin_chat_id = settings.ADMIN_CHAT_ID
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat (id, name, created_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            [admin_chat_id, 'Carga administrativa de documentos', actor_user_id],
        )
    return admin_chat_id


class DocumentUploadForm(forms.ModelForm):
    """Used for the create view."""
    name = forms.CharField(max_length=255, label='Nombre')
    description = forms.CharField(
        label='Descripción',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    raw_collection = forms.FileField(label='Archivo', required=True)

    class Meta:
        model = Document
        fields = []

    def _post_clean(self):
        pass


class DocumentChangeForm(forms.ModelForm):
    """Used for the change view — all fields are readonly."""

    class Meta:
        model = Document
        fields = []

    def _post_clean(self):
        pass


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'description_short',
        'size_display',
        'collection_count',
        'status',
        'modified_date',
        'created_by_display',
    )
    list_filter = ('status', 'created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'description')
    readonly_fields = (
        'id',
        'name',
        'description',
        'size_display',
        'status',
        'mime_type',
        'storage_url',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'size_display', 'status', 'mime_type'),
        }),
        ('Almacenamiento', {
            'fields': ('storage_url',),
            'classes': ('collapse',),
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted_at__isnull=True)

    def changelist_view(self, request, extra_context=None):
        # Batch-fetch collection counts to avoid N+1.
        try:
            with connections['aura_db'].cursor() as cursor:
                cursor.execute("""
                    SELECT document_id, COUNT(*)
                    FROM document_in_document_collection
                    WHERE deleted_at IS NULL
                    GROUP BY document_id
                """)
                self._collection_counts = dict(cursor.fetchall())
        except Exception:
            self._collection_counts = {}
        return super().changelist_view(request, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        return DocumentUploadForm if obj is None else DocumentChangeForm

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Subir documento', {
                    'fields': ('name', 'description', 'raw_collection'),
                }),
            )
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return self.readonly_fields
        return ('id',)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._changeform_view(request, object_id, form_url, extra_context)

    def _changeform_view(self, request, object_id, form_url, extra_context):
        # Change view — fully readonly, delegate to Django default.
        if object_id is not None:
            return super()._changeform_view(request, object_id, form_url, extra_context)

        # Create view GET — delegate to Django default.
        if request.method != 'POST':
            return super()._changeform_view(request, object_id, form_url, extra_context)

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField(
                'The field %s cannot be referenced.' % to_field
            )
        if not self.has_add_permission(request):
            raise PermissionDenied

        form_class = self.get_form(request, None)
        form = form_class(request.POST, request.FILES)

        if not form.is_valid():
            # Re-render with errors.
            fieldsets = self.get_fieldsets(request, None)
            admin_form = helpers.AdminForm(
                form,
                list(fieldsets),
                {},
                (),
                model_admin=self,
            )
            context = {
                **self.admin_site.each_context(request),
                'title': _('Add %s') % self.opts.verbose_name,
                'subtitle': None,
                'adminform': admin_form,
                'object_id': None,
                'original': None,
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                'media': self.media + admin_form.media,
                'inline_admin_formsets': [],
                'errors': helpers.AdminErrorList(form, []),
                'preserved_filters': self.get_preserved_filters(request),
            }
            context.update(extra_context or {})
            return self.render_change_form(request, context, add=True, change=False, obj=None, form_url=form_url)

        raw_collection = form.cleaned_data['raw_collection']
        try:
            chat_id = _ensure_admin_chat(request.user.pk)
            response_payload = create_document_from_admin(
                raw_document=raw_collection,
                chat_id=chat_id,
                actor_user=request.user,
            )
        except DocumentProcessingServiceError as exc:
            form.add_error(None, str(exc))
            fieldsets = self.get_fieldsets(request, None)
            admin_form = helpers.AdminForm(form, list(fieldsets), {}, (), model_admin=self)
            context = {
                **self.admin_site.each_context(request),
                'title': _('Add %s') % self.opts.verbose_name,
                'subtitle': None,
                'adminform': admin_form,
                'object_id': None,
                'original': None,
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                'media': self.media + admin_form.media,
                'inline_admin_formsets': [],
                'errors': helpers.AdminErrorList(form, []),
                'preserved_filters': self.get_preserved_filters(request),
            }
            return self.render_change_form(request, context, add=True, change=False, obj=None, form_url=form_url)

        document_id = response_payload.get('id')

        try:
            new_object = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            new_object = Document(pk=document_id, name=form.cleaned_data.get('name', ''))

        log_audit(
            actor=request.user,
            action='CREATE',
            entity_type='Document',
            entity_id=str(document_id),
            entity_label=new_object.name,
            source='admin',
        )
        return self.response_add(request, new_object)

    # ── List display helpers ─────────────────────────────────────────────────

    def description_short(self, obj):
        if not obj.description:
            return '-'
        return obj.description[:80] + ('…' if len(obj.description) > 80 else '')
    description_short.short_description = 'Descripción'

    def size_display(self, obj):
        if not obj.file_size_bytes:
            return '-'
        size = float(obj.file_size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    size_display.short_description = 'Tamaño'
    size_display.admin_order_field = 'file_size_bytes'

    def collection_count(self, obj):
        count = getattr(self, '_collection_counts', {}).get(obj.pk, 0)
        return format_html(
            '<span style="background:#417690;color:#fff;padding:3px 10px;border-radius:3px;">{}</span>',
            count,
        )
    collection_count.short_description = 'Colecciones'

    def modified_date(self, obj):
        if obj.updated_at:
            return obj.updated_at.strftime('%d/%m/%Y')
        return '-'
    modified_date.short_description = 'Modificado'
    modified_date.admin_order_field = 'updated_at'

    def created_by_display(self, obj):
        return obj.created_by or '-'
    created_by_display.short_description = 'Subido por'

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='Document',
            entity_id=str(obj.pk),
            entity_label=obj.name,
            details={'deleted_at': str(obj.deleted_at)},
            source='admin',
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='Document',
                entity_id=str(obj.pk),
                entity_label=obj.name,
                details={'deleted_at': str(obj.deleted_at)},
                source='admin',
            )
