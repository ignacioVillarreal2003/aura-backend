"""Custom group admin configuration."""

import logging
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from accounts.models import CustomGroup, User
from accounts.admin_parts.common import (
    HelpTextStripMixin,
    apply_audit_fields,
    is_admin_or_super_user,
    is_super_admin_user,
    log_audit,
    count_badge,
    truncate_description,
)
from accounts.repositories import group_membership as gm_repo
from accounts.services.group_service import sync_group_to_collection, soft_delete_collection

logger = logging.getLogger(__name__)


class CustomGroupAdminForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(deleted_at__isnull=True).order_by('username'),
        required=False,
        widget=FilteredSelectMultiple('Usuarios', is_stacked=False),
        label='Usuarios',
    )

    class Meta:
        model = CustomGroup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            try:
                user_ids = gm_repo.get_user_ids_for_group(self.instance.pk)
                self.initial['users'] = user_ids
            except Exception:
                logger.exception('Failed to load users for CustomGroupAdminForm')


@admin.register(CustomGroup)
class CustomGroupAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Custom admin for Group model to manage groups."""

    form = CustomGroupAdminForm
    list_display = ('name', 'description_short', 'member_count', 'document_count')
    list_filter = ('created_at',)
    search_fields = ('name',)
    filter_horizontal = ('documents',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'documents'),
        }),
        ('Miembros', {
            'fields': ('users',),
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
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )

    def description_short(self, obj):
        return truncate_description(obj.description)
    description_short.short_description = 'Descripción'

    def member_count(self, obj):
        count = gm_repo.count_members_for_group(obj.pk)
        return count_badge(count)
    member_count.short_description = 'Miembros'

    def document_count(self, obj):
        return count_badge(obj.documents.count())
    document_count.short_description = 'Documentos'

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Información Básica', {
                    'fields': ('name', 'description', 'documents'),
                }),
                ('Miembros', {
                    'fields': ('users',),
                }),
            )
        return self.fieldsets

    def has_module_permission(self, request):
        return is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return is_admin_or_super_user(request.user)

    def has_change_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'users' not in form.cleaned_data:
            return
        selected_users = list(form.cleaned_data['users'])
        user_ids = [u.pk for u in selected_users]
        try:
            gm_repo.set_users_for_group(form.instance.pk, user_ids)
        except Exception:
            logger.exception('Failed to sync users for CustomGroup %s', form.instance.pk)

    def save_model(self, request, obj, form, change):
        old_name = None
        if obj.pk:
            old_name = CustomGroup.objects.filter(pk=obj.pk).values_list('name', flat=True).first()
        apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        sync_group_to_collection(obj, request.user.pk, old_name=old_name, is_create=not change)
        log_audit(
            actor=request.user,
            action='UPDATE' if change else 'CREATE',
            entity_type='custom_group',
            entity_id=str(obj.pk),
            entity_label=obj.name,
            details={'changed_fields': form.changed_data} if change and form.changed_data else None,
        )

    def delete_model(self, request, obj):
        soft_delete_collection(obj, request.user.pk)
        super().delete_model(request, obj)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='custom_group',
            entity_id=str(obj.pk),
            entity_label=obj.name,
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            soft_delete_collection(obj, request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='custom_group',
                entity_id=str(obj.pk),
                entity_label=obj.name,
            )
        super().delete_queryset(request, queryset)
