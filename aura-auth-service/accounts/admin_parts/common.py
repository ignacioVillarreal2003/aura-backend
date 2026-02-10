"""Common admin utilities for accounts app."""

from django.contrib import admin
from accounts.models import User


class StatusFilter(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'estado'

    def lookups(self, request, model_admin):
        return (
            ('activo', 'Activo'),
            ('inactivo', 'Inactivo'),
            ('eliminado', 'Eliminado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'activo':
            return queryset.filter(status='active', is_active=True, deleted_at__isnull=True)
        if value == 'inactivo':
            return queryset.filter(status='inactive', deleted_at__isnull=True)
        if value == 'eliminado':
            return queryset.filter(deleted_at__isnull=False)
        return queryset


class EnabledFilter(admin.SimpleListFilter):
    title = 'Habilitado'
    parameter_name = 'enabled'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Habilitado'),
            ('0', 'Deshabilitado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == '1':
            return queryset.filter(is_active=True)
        if value == '0':
            return queryset.filter(is_active=False)
        return queryset


class CreatedDateFilter(admin.DateFieldListFilter):
    title = 'Creado'


def _apply_audit_fields(obj, actor, is_create: bool):
    if is_create and not obj.created_by_id:
        obj.created_by = actor
    obj.updated_by = actor


def _is_super_admin_user(user: User) -> bool:
    return bool(user and user.is_superuser)


class HelpTextStripMixin:
    """Remove help text from admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield


class HelpTextStripInlineMixin:
    """Remove help text from inline admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield
