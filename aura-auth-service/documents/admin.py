"""Django Admin customization for document models."""

from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.contrib.admin.utils import flatten_fieldsets, unquote
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, router, transaction
from django.forms.formsets import all_valid
from django.utils.translation import gettext as _
from django.utils.html import format_html
from accounts.models import CustomGroup, FauRole
from documents.models import Document
from documents.services.document_processing_client import (
    DocumentProcessingServiceError,
    create_document_from_admin,
)


ADMIN_CHAT_ID = 12345


def _apply_audit_fields(obj, username: str, is_create: bool):
    if is_create and not obj.created_by:
        obj.created_by = username
    obj.updated_by = username


def _ensure_admin_chat(actor_user_id: int) -> int:
    """Ensure the shared admin chat exists in aura_db for document-processing."""

    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat (id, name, created_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            [ADMIN_CHAT_ID, 'Carga administrativa de documentos', actor_user_id],
        )
    return ADMIN_CHAT_ID


class DocumentUploadForm(forms.ModelForm):
    description = forms.CharField(
        label='Descripción',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    raw_collection = forms.FileField(
        label='Documento',
        required=True,
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.filter(deleted_at__isnull=True).order_by('name'),
        required=False,
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        label='Grupos',
        help_text='',
    )
    minimum_fau_role = forms.ModelChoiceField(
        queryset=FauRole.objects.order_by('power', 'name'),
        required=False,
        label='Rol FAU mínimo',
        help_text='Ese rol y todos los de mayor jerarquía podrán acceder.',
    )
    visible_to_all = forms.BooleanField(
        required=False,
        label='Disponible para todos',
        help_text='Si está activo, no se aplican restricciones por grupos ni jerarquía FAU.',
    )

    class Meta:
        model = Document
        fields = ('name', 'description', 'raw_collection', 'groups', 'minimum_fau_role', 'visible_to_all')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding:
            self.fields['raw_collection'].required = False
            self.fields['groups'].initial = self.instance.groups.all()

    def clean(self):
        cleaned_data = super().clean()
        visible_to_all = cleaned_data.get('visible_to_all')
        minimum_fau_role = cleaned_data.get('minimum_fau_role')
        if not visible_to_all and minimum_fau_role is None:
            raise ValidationError('Debes marcar "Disponible para todos" o seleccionar un Rol FAU mínimo.')
        return cleaned_data


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin for Document model.
    """
    list_display = (
        'name',
        'description',
        'size_display',
        'group_count',
        'access_scope_display',
        'modified_date',
        'created_by_display',
    )
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'description')
    readonly_fields = (
        'id',
        'external_document_id',
        'external_storage_url',
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
            'fields': ('id', 'name', 'description', 'size_bytes'),
        }),
        ('Acceso', {
            'fields': ('visible_to_all', 'minimum_fau_role', 'groups'),
        }),
        ('Integración', {
            'fields': ('external_document_id', 'external_storage_url'),
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
                    'fields': ('name', 'description', 'raw_collection'),
                }),
                ('Acceso', {
                    'fields': ('visible_to_all', 'minimum_fau_role', 'groups'),
                }),
            )
        return self.fieldsets

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = DocumentUploadForm
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('minimum_fau_role').prefetch_related('groups')

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._changeform_view(request, object_id, form_url, extra_context)

    def _changeform_view(self, request, object_id, form_url, extra_context):
        if object_id is not None or request.method != 'POST':
            return super()._changeform_view(request, object_id, form_url, extra_context)

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField(
                'The field %s cannot be referenced.' % to_field
            )

        if not self.has_add_permission(request):
            raise PermissionDenied

        fieldsets = self.get_fieldsets(request, None)
        ModelForm = self.get_form(
            request,
            None,
            change=False,
            fields=flatten_fieldsets(fieldsets),
        )
        form = ModelForm(request.POST, request.FILES)
        formsets, inline_instances = self._create_formsets(
            request,
            form.instance,
            change=False,
        )
        form_validated = form.is_valid()
        if form_validated:
            new_object = self.save_form(request, form, change=False)
        else:
            new_object = form.instance

        if all_valid(formsets) and form_validated:
            try:
                self.save_model(request, new_object, form, False)
            except DocumentProcessingServiceError as exc:
                form.add_error(None, str(exc))
                form_validated = False
            else:
                self.save_related(request, form, formsets, False)
                change_message = self.construct_change_message(
                    request,
                    form,
                    formsets,
                    True,
                )
                self.log_addition(request, new_object, change_message)
                return self.response_add(request, new_object)

        admin_form = helpers.AdminForm(
            form,
            list(fieldsets),
            self.get_prepopulated_fields(request, None),
            self.get_readonly_fields(request, None),
            model_admin=self,
        )
        media = self.media + admin_form.media
        inline_formsets = self.get_inline_formsets(
            request,
            formsets,
            inline_instances,
            None,
        )
        for inline_formset in inline_formsets:
            media += inline_formset.media

        context = {
            **self.admin_site.each_context(request),
            'title': _('Add %s') % self.opts.verbose_name,
            'subtitle': None,
            'adminform': admin_form,
            'object_id': object_id,
            'original': None,
            'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            'to_field': to_field,
            'media': media,
            'inline_admin_formsets': inline_formsets,
            'errors': helpers.AdminErrorList(form, formsets),
            'preserved_filters': self.get_preserved_filters(request),
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            add=True,
            change=False,
            obj=None,
            form_url=form_url,
        )

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

    def created_by_display(self, obj):
        return obj.created_by or '-'
    created_by_display.short_description = 'Subido por'

    def group_count(self, obj):
        count = obj.groups.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count,
        )
    group_count.short_description = 'Grupos'

    def access_scope_display(self, obj):
        if obj.visible_to_all:
            return format_html('<span style="color: green; font-weight: bold;">Todos</span>')
        if obj.minimum_fau_role_id:
            return format_html(
                '<span style="color: #417690; font-weight: bold;">{} y superiores</span>',
                obj.minimum_fau_role.name,
            )
        return '-'
    access_scope_display.short_description = 'Acceso'

    def save_model(self, request, obj, form, change):
        if change:
            if obj.visible_to_all:
                obj.minimum_fau_role = None
            _apply_audit_fields(obj, request.user.username, is_create=False)
            super().save_model(request, obj, form, change)
            if obj.visible_to_all:
                obj.groups.clear()
            else:
                obj.groups.set(form.cleaned_data.get('groups'))
            return

        description = form.cleaned_data.get('description')
        raw_collection = form.cleaned_data.get('raw_collection')
        if not raw_collection:
            raise ValidationError('Debe seleccionar un documento.')
        chat_id = _ensure_admin_chat(request.user.pk)

        response_payload = create_document_from_admin(
            raw_document=raw_collection,
            chat_id=chat_id,
            actor_user=request.user,
        )

        obj.description = description
        obj.size_bytes = raw_collection.size or 0
        obj.external_document_id = response_payload.get('id')
        obj.external_storage_url = response_payload.get('storage_url', '')
        obj.visible_to_all = form.cleaned_data.get('visible_to_all', False)
        obj.minimum_fau_role = None if obj.visible_to_all else form.cleaned_data.get('minimum_fau_role')
        _apply_audit_fields(obj, request.user.username, is_create=True)
        super().save_model(request, obj, form, change)
        if obj.visible_to_all:
            obj.groups.clear()
        else:
            obj.groups.set(form.cleaned_data.get('groups'))


