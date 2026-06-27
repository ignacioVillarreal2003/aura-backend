"""Filtros del admin para la app accounts."""

from django.contrib import admin


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
            return queryset.filter(status='active', deleted_at__isnull=True)
        if value == 'inactivo':
            return queryset.filter(status='inactive', deleted_at__isnull=True)
        if value == 'eliminado':
            return queryset.filter(deleted_at__isnull=False)
        return queryset


class CreatedDateFilter(admin.DateFieldListFilter):
    title = 'Creado'
