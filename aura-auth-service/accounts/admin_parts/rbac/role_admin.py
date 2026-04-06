"""Role admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import Role
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user


@admin.register(Role)
class RoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Role model."""

    list_display = ('name', 'description_short', 'permission_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        if not _is_super_admin_user(request.user):
            return False
        if obj is None:
            return True
        if obj.name in ['SUPER_ADMIN', 'ADMIN']:
            return False
        if request.user and obj.user_assignments.filter(
            user=request.user,
            deleted_at__isnull=True,
        ).exists():
            return False
        return True

    def delete_queryset(self, request, queryset):
        if not _is_super_admin_user(request.user):
            return
        protected = queryset.filter(
            name__in=['SUPER_ADMIN', 'ADMIN']
        ) | queryset.filter(
            user_assignments__user=request.user,
            user_assignments__deleted_at__isnull=True,
        )
        safe_queryset = queryset.exclude(id__in=protected.values_list('id', flat=True))
        super().delete_queryset(request, safe_queryset)

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        count = obj.permission_links.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'
