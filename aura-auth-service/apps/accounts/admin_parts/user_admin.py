"""Configuracion del admin de usuarios."""

import json
import logging

from django.contrib import admin, messages
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

logger = logging.getLogger(__name__)
from apps.accounts.models import User, Role, UserRole
from apps.accounts.admin_parts.common import (
    StatusFilter,
    CreatedDateFilter,
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
    _is_admin_or_super_user,
    _is_effective_superadmin,
    log_audit,
    has_permission,
)
from apps.accounts.admin_parts.forms.user_form import UserAdminForm


def _can_see_full_user_edit(request, obj):
    """True cuando el editor puede ver Grupos + Auditoría en el formulario de un user."""
    if has_permission(request, 'ADMIN_USERS_EDIT_ADMIN'):
        return True
    if not obj:
        return False
    return (
        has_permission(request, 'ADMIN_USERS_EDIT') and
        obj.user_roles.filter(role__name='user', deleted_at__isnull=True).exists()
    )


@admin.action(description='Forzar cierre de sesión inmediato')
def force_logout(modeladmin, request, queryset):
    """Invalida inmediatamente todas las sesiones activas de los usuarios seleccionados.

    Setea force_logout_at=now() para que cualquier access token emitido antes
    de ese momento sea rechazado al validarse, y revoca todos los refresh tokens.
    """
    from apps.accounts.models import RefreshToken

    now = timezone.now()
    count = 0
    for user in queryset:
        user.force_logout_at = now
        user.save(update_fields=['force_logout_at', 'updated_at'])
        RefreshToken.objects.filter(user=user, is_revoked=False).update(
            is_revoked=True,
            updated_at=now,
        )
        log_audit(
            actor=request.user,
            action='FORCE_LOGOUT',
            entity_type='auth_user',
            entity_id=user.pk,
            entity_label=user.username,
            source='admin',
        )
        count += 1

    modeladmin.message_user(
        request,
        f'Sesión forzada para {count} usuario(s). Sus tokens quedan invalidados de inmediato.',
        messages.SUCCESS,
    )


@admin.register(User)
class UserAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin a medida para el modelo User."""

    class RoleFilter(admin.SimpleListFilter):
        title = 'Rol'
        parameter_name = 'rol'

        def lookups(self, request, model_admin):
            roles = Role.objects.order_by('name').values_list('name', flat=True)
            return [(name, name) for name in roles]

        def queryset(self, request, queryset):
            value = self.value()
            if not value:
                return queryset
            return queryset.filter(
                user_roles__role__name=value,
                user_roles__deleted_at__isnull=True,
            )

    list_display = (
        'username',
        'name',
        'roles_display',
        'status_badge',
        'last_login_display',
    )
    list_filter = (
        RoleFilter,
        StatusFilter,
        ('created_at', CreatedDateFilter),
    )
    search_fields = ('username', 'email')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
        'last_login',
        'last_password_change',
    )

    form = UserAdminForm
    change_form_template = 'admin/accounts/user/change_form.html'
    actions = [force_logout]
    actions_selection_counter = False

    fieldsets = (
        ('Identidad', {
            'fields': ('roles', 'username', 'name', 'email', 'password', 'active'),
        }),
    )

    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#10007; Eliminado</span>'
            )
        if obj.status == 'active':
            return format_html(
                '<span style="color: green; font-weight: bold;">&#10003; Activo</span>'
            )
        return format_html(
            '<span style="color: #d96c6c; font-weight: bold;">&#x2753; Inactivo</span>'
        )
    status_badge.short_description = 'Estado'

    def roles_display(self, obj):
        if obj.is_deleted:
            roles = obj.user_roles.values_list('role__name', flat=True).distinct()
        else:
            roles = obj.user_roles.filter(deleted_at__isnull=True).values_list('role__name', flat=True)
        labels = []
        for role in roles:
            if role == 'user':
                labels.append('user')
            else:
                labels.append(role)
        return ', '.join(labels) if labels else '-'
    roles_display.short_description = 'Rol'

    def created_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return '-'
    created_date.short_description = 'Creado'
    created_date.admin_order_field = 'created_at'

    def created_by_display(self, obj):
        if obj.is_superuser and obj.created_by and obj.created_by.is_superuser:
            return 'Administracion'
        if obj.created_by:
            return obj.created_by.username
        return '-'
    created_by_display.short_description = 'Creado por'
    created_by_display.admin_order_field = 'created_by__username'

    def last_login_display(self, obj):
        if obj.last_login:
            return obj.last_login.strftime('%d/%m/%Y %H:%M')
        return '-'
    last_login_display.short_description = 'Ultimo login'
    last_login_display.admin_order_field = 'last_login'

    def mac_profile_link(self, obj):
        url = reverse('admin:mac_user_mac', args=[obj.pk])
        return format_html(
            '<a href="{}" style="'
            'display:inline-block;padding:3px 9px;background:#205067;color:#fff;'
            'border-radius:4px;font-size:11px;font-weight:600;text-decoration:none;'
            '">MAC</a>',
            url,
        )
    mac_profile_link.short_description = 'Perfil MAC'
    mac_profile_link.allow_tags = True

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        if not (_is_effective_superadmin(request) or has_permission(request, 'ADMIN_USERS_EDIT_ADMIN')):
            actions.pop('action_force_logout', None)
        return actions

    def action_force_logout(self, request, queryset):
        """Cierra todas las sesiones activas de los usuarios seleccionados."""
        from apps.accounts.services.auth_service import revoke_all_sessions

        count = 0
        for user in queryset:
            revoke_all_sessions(user)
            count += 1
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='auth_user',
                entity_id=user.pk,
                entity_label=user.username,
                details={'force_logout': True},
                source='admin',
                request=request,
            )
        messages.success(request, f'Se cerraron todas las sesiones de {count} usuario(s).')
    action_force_logout.short_description = 'Cerrar todas las sesiones (forzar logout)'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('username', 'email', 'roles_display')
        return self.readonly_fields

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['is_superadmin'] = _is_effective_superadmin(request)
        return super().changelist_view(request, extra_context=extra_context)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            role_type = request.GET.get('role', 'user')
            if role_type == 'user':
                return (
                    ('Identidad', {
                        'fields': ('username', 'name', 'email', 'password', 'active'),
                    }),
                    ('Grupos', {
                        'fields': ('classification_level_id',),
                    }),
                )
            return (
                ('Identidad', {
                    'fields': ('username', 'name', 'email', 'password', 'active'),
                }),
            )
        is_superadmin_obj = obj and obj.user_roles.filter(
            role__name='superadmin', deleted_at__isnull=True
        ).exists()
        if is_superadmin_obj:
            return (
                ('Identidad', {
                    'fields': ('roles_display', 'username', 'email'),
                }),
            )
        if _can_see_full_user_edit(request, obj):
            is_admin_obj = obj and obj.user_roles.filter(
                role__name='admin', deleted_at__isnull=True
            ).exists()
            grupos_label = 'Grupos - Modo usuario' if is_admin_obj else 'Grupos'
            return (
                ('Identidad', {
                    'fields': ('roles_display', 'username', 'name', 'email', 'active'),
                }),
                (grupos_label, {
                    'fields': ('classification_level_id',),
                }),
                ('Auditoría', {
                    'fields': (
                        'created_by',
                        'created_at',
                        'updated_by',
                        'updated_at',
                        'last_login',
                        'last_password_change',
                        'deleted_by',
                        'deleted_at',
                    ),
                }),
            )
        return (
            ('Identidad', {
                'fields': ('roles_display', 'username', 'name', 'email', 'active'),
            }),
        )

    def get_form(self, request, obj=None, **kwargs):
        from django import forms as dj_forms
        from apps.accounts.services.mac_client import mac_client

        form = super().get_form(request, obj, **kwargs)
        for field_name in ('created_by', 'updated_by', 'deleted_by'):
            if field_name in form.base_fields:
                form.base_fields.pop(field_name)
        for field_name in ('username', 'email'):
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = ''

        if obj:
            for field_name in ('roles', 'password', 'compartment_ids'):
                form.base_fields.pop(field_name, None)
            audit_labels = {
                'created_by': 'Creado por',
                'created_at': 'Fecha creado',
                'updated_by': 'Actualizado por',
                'updated_at': 'Fecha actualizado',
                'last_login': 'Ultimo inicio de sesion',
                'last_password_change': 'Ultimo cambio de contrasena',
                'deleted_by': 'Eliminado por',
                'deleted_at': 'Fecha eliminado',
            }
            for field_name, label in audit_labels.items():
                if field_name in form.base_fields:
                    form.base_fields[field_name].label = label
            if _can_see_full_user_edit(request, obj):
                choices = getattr(request, '_mac_level_choices', [('', '-- Sin nivel --')])
                initial = getattr(request, '_mac_current_level_id', '')
                form.base_fields['classification_level_id'] = dj_forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label='Nivel',
                    initial=initial,
                )
            else:
                form.base_fields.pop('classification_level_id', None)
        else:
            form.base_fields.pop('roles', None)

            role_type = request.GET.get('role', 'user')
            if role_type == 'user':
                try:
                    levels = sorted(
                        mac_client.list_classification_levels(request.user),
                        key=lambda x: x.get('rank', 0),
                    )
                except Exception:
                    levels = []
                try:
                    compartments = mac_client.list_compartments(request.user)
                except Exception:
                    compartments = []
                form.base_fields['classification_level_id'] = dj_forms.ChoiceField(
                    choices=[('', '-- Sin nivel --')] + [
                        (str(l['id']), l['name']) for l in levels
                    ],
                    required=False,
                    label='Nivel',
                )
                form.base_fields.pop('compartment_ids', None)
            else:
                form.base_fields.pop('classification_level_id', None)
                form.base_fields.pop('compartment_ids', None)

        return form

    def get_list_filter(self, request):
        return self.list_filter

    def get_queryset(self, request):
        from datetime import timedelta
        one_week_ago = timezone.now() - timedelta(days=7)
        queryset = super().get_queryset(request)
        queryset = (
            queryset
            .filter(Q(deleted_at__isnull=True) | Q(deleted_at__gte=one_week_ago))
            .prefetch_related('user_roles__role')
            .order_by(F('deleted_at').asc(nulls_first=True), 'username')
        )
        if not (has_permission(request, 'ADMIN_USERS_VIEW_ADMINS') or _is_effective_superadmin(request)):
            queryset = queryset.filter(
                user_roles__role__name='user',
                user_roles__deleted_at__isnull=True,
            )
        return queryset

    def has_add_permission(self, request):
        if has_permission(request, 'ADMIN_USERS_CREATE'):
            return True
        return bool(request.user and request.user.is_staff)

    def has_module_permission(self, request):
        if has_permission(request, 'ADMIN_USERS_VIEW'):
            return True
        return bool(request.user and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if has_permission(request, 'ADMIN_USERS_VIEW'):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_deleted:
            return False
        if obj is not None and obj.user_roles.filter(role__name='superadmin', deleted_at__isnull=True).exists():
            return False
        if obj is not None and obj.user_roles.filter(role__name='admin', deleted_at__isnull=True).exists():
            if not has_permission(request, 'ADMIN_USERS_EDIT_ADMIN'):
                return False
        if has_permission(request, 'ADMIN_USERS_EDIT'):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_deleted:
            return False
        if obj is not None and obj.user_roles.filter(role__name='superadmin', deleted_at__isnull=True).exists():
            return False
        if obj is not None and obj.user_roles.filter(role__name='admin', deleted_at__isnull=True).exists():
            if not has_permission(request, 'ADMIN_USERS_DELETE_ADMIN'):
                return False
        if has_permission(request, 'ADMIN_USERS_DELETE'):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    class Media:
        js = ('accounts/admin/user_password.js',)

        css = {
            "all": ("accounts/admin/custom.css",)
        }

    def add_view(self, request, form_url='', extra_context=None):
        from django.core.exceptions import PermissionDenied
        extra_context = extra_context or {}
        if request.GET.get('role') == 'admin':
            if not (has_permission(request, 'ADMIN_USERS_CREATE_ADMIN') or _is_effective_superadmin(request)):
                raise PermissionDenied
            extra_context['custom_verbose_name'] = 'Administrador'
        if request.GET.get('role', 'user') == 'user':
            from apps.accounts.services.mac_client import mac_client
            try:
                compartments = mac_client.list_compartments(request.user)
            except Exception:
                compartments = []
            extra_context['compartments_json'] = json.dumps([
                {'id': str(c['id']), 'label': c['name']}
                for c in compartments
            ])
            extra_context['assigned_comp_ids_json'] = json.dumps([])
            extra_context['show_compartments_panel'] = True
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['subtitle'] = None
        try:
            uid = int(object_id)
            roles = list(
                UserRole.objects.filter(user_id=uid, deleted_at__isnull=True)
                .values_list('role__name', flat=True)
            )
            if 'superadmin' in roles:
                extra_context['custom_verbose_name'] = 'Superadmin'
                extra_context['view_only_user'] = True
            elif 'admin' in roles:
                extra_context['custom_verbose_name'] = 'Administrador'
            else:
                extra_context['custom_verbose_name'] = 'Usuario'
        except (ValueError, Exception):
            pass

        is_user_type = extra_context.get('custom_verbose_name') == 'Usuario'
        can_load_mac = (
            not extra_context.get('view_only_user') and (
                has_permission(request, 'ADMIN_USERS_EDIT_ADMIN') or
                (has_permission(request, 'ADMIN_USERS_MAC') and is_user_type)
            )
        )
        if object_id and can_load_mac:
            from apps.accounts.services.mac_client import mac_client, MacServiceError
            try:
                levels = sorted(
                    mac_client.list_classification_levels(request.user),
                    key=lambda x: x.get('rank', 0),
                )
            except MacServiceError:
                levels = []
            try:
                all_compartments = mac_client.list_compartments(request.user)
            except MacServiceError:
                all_compartments = []
            try:
                auth_data = mac_client.get_user_authorization(request.user, int(object_id))
            except MacServiceError:
                auth_data = {}
            clearance = auth_data.get('clearance') if auth_data else None
            user_compartments = auth_data.get('compartments', []) if auth_data else []
            current_level_id = (
                str(clearance['classification_level']['id'])
                if clearance and clearance.get('classification_level')
                else ''
            )
            assigned_comp_ids = [
                str(uc.get('compartment', {}).get('id'))
                for uc in user_compartments
                if uc.get('compartment', {}).get('id')
            ]
            request._mac_level_choices = (
                [('', '-- Sin nivel --')] + [(str(l['id']), l['name']) for l in levels]
            )
            request._mac_current_level_id = current_level_id
            extra_context.update({
                'compartments_json': json.dumps([
                    {'id': str(c['id']), 'label': c['name']}
                    for c in all_compartments
                ]),
                'assigned_comp_ids_json': json.dumps(assigned_comp_ids),
                'show_compartments_panel': True,
            })

        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        if 'active' in form.cleaned_data:
            obj.status = 'active' if form.cleaned_data['active'] else 'inactive'
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)

        if change:
            changes = {}

            if 'active' in form.changed_data:
                changes['activo'] = obj.status == 'active'

            if _can_see_full_user_edit(request, obj):
                from apps.accounts.services.mac_client import mac_client, MacServiceError
                cl_id = (form.cleaned_data.get('classification_level_id') or '').strip()
                comp_ids = request.POST.getlist('compartment_ids')

                try:
                    auth_data = mac_client.get_user_authorization(request.user, obj.pk)
                    current_comp_ids = {
                        uc.get('compartment', {}).get('id')
                        for uc in (auth_data.get('compartments', []) if auth_data else [])
                        if uc.get('compartment', {}).get('id')
                    }
                    prev_clearance = auth_data.get('clearance') if auth_data else None
                    prev_level_id = (
                        str(prev_clearance['classification_level']['id'])
                        if prev_clearance and prev_clearance.get('classification_level')
                        else ''
                    )
                except Exception:
                    current_comp_ids = set()
                    prev_level_id = ''

                if cl_id:
                    try:
                        mac_client.set_user_clearance(request.user, obj.pk, int(cl_id))
                    except Exception as exc:
                        logger.warning('Could not set clearance for user %s: %s', obj.pk, exc)
                else:
                    try:
                        mac_client.delete_user_clearance(request.user, obj.pk)
                    except Exception:
                        pass

                new_comp_ids = set(int(c) for c in comp_ids if c)
                for cid in new_comp_ids - current_comp_ids:
                    try:
                        mac_client.add_user_compartment(request.user, obj.pk, cid)
                    except Exception as exc:
                        logger.warning('Could not add compartment %s for user %s: %s', cid, obj.pk, exc)
                for cid in current_comp_ids - new_comp_ids:
                    try:
                        mac_client.remove_user_compartment(request.user, obj.pk, cid)
                    except Exception as exc:
                        logger.warning('Could not remove compartment %s for user %s: %s', cid, obj.pk, exc)

                if cl_id != prev_level_id:
                    if cl_id:
                        nivel_nombre = cl_id
                        level_field = form.fields.get('classification_level_id')
                        if level_field:
                            for choice_id, choice_name in level_field.choices:
                                if str(choice_id) == str(cl_id):
                                    nivel_nombre = choice_name
                                    break
                        changes['nivel'] = nivel_nombre
                    else:
                        changes['nivel'] = None

                if new_comp_ids != current_comp_ids:
                    try:
                        all_compartments = mac_client.list_compartments(request.user)
                        comp_map = {str(c['id']): c['name'] for c in all_compartments}
                        changes['agrupaciones'] = [
                            comp_map.get(str(cid), str(cid)) for cid in sorted(new_comp_ids)
                        ]
                    except Exception:
                        changes['agrupaciones'] = [str(cid) for cid in sorted(new_comp_ids)]

            permission_keys = {'nivel', 'agrupaciones'}
            has_permission_change = bool(changes.keys() & permission_keys)
            if has_permission_change and _is_effective_superadmin(request):
                label = f'Superadmin {request.user.username} actualizó permisos MAC de {obj.username}'
            else:
                label = f'{request.user.username} modificó usuario {obj.username}'
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=label,
                details=changes if changes else None,
                request=request,
            )
        else:
            from apps.accounts.services.mac_client import mac_client
            role_type = request.GET.get('role', 'user')
            if role_type == 'admin' and not (has_permission(request, 'ADMIN_USERS_CREATE_ADMIN') or _is_effective_superadmin(request)):
                role_type = 'user'
            try:
                role = Role.objects.get(name=role_type)
                UserRole.objects.create(user=obj, role=role, created_by=request.user)
            except Role.DoesNotExist:
                pass

            nivel_nombre = None
            agrupaciones = []

            if role_type == 'user':
                cl_id = form.cleaned_data.get('classification_level_id', '')
                comp_ids = request.POST.getlist('compartment_ids')
                if cl_id:
                    try:
                        mac_client.set_user_clearance(request.user, obj.pk, int(cl_id))
                    except Exception as exc:
                        logger.warning('Could not set clearance for user %s: %s', obj.pk, exc)
                for comp_id in comp_ids:
                    try:
                        mac_client.add_user_compartment(request.user, obj.pk, int(comp_id))
                    except Exception as exc:
                        logger.warning('Could not add compartment %s for user %s: %s', comp_id, obj.pk, exc)

                level_field = form.fields.get('classification_level_id')
                if cl_id and level_field:
                    for choice_id, choice_name in level_field.choices:
                        if str(choice_id) == str(cl_id):
                            nivel_nombre = choice_name
                            break

                if comp_ids:
                    try:
                        all_compartments = mac_client.list_compartments(request.user)
                        comp_map = {str(c['id']): c['name'] for c in all_compartments}
                        agrupaciones = [comp_map.get(str(cid), str(cid)) for cid in comp_ids if cid]
                    except Exception:
                        agrupaciones = [str(cid) for cid in comp_ids if cid]

            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=f'{request.user.username} creó usuario {obj.username}',
                details={
                    'usuario': obj.username,
                    'correo': obj.email,
                    'activo': obj.status == 'active',
                    'rol': role_type,
                    'nivel': nivel_nombre,
                    'agrupaciones': agrupaciones,
                },
                request=request,
            )

    def delete_model(self, request, obj):
        UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
            deleted_at=timezone.now(),
            deleted_by_id=request.user.pk,
        )
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
            request=request,
        )

    def delete_queryset(self, request, queryset):
        now = timezone.now()
        for obj in queryset:
            UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_by_id=request.user.pk,
            )
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=obj.username,
                request=request,
            )

    def history_view(self, request, object_id, extra_context=None):
        from django.core.exceptions import PermissionDenied
        from django.template.response import TemplateResponse
        from apps.accounts.admin_parts.utils.history import build_entity_history

        if not self.has_view_permission(request):
            raise PermissionDenied

        try:
            obj = self.get_object(request, object_id)
        except Exception:
            obj = None

        entity_name = obj.username if obj else object_id
        entries = build_entity_history('auth_user', object_id)
        back_url = reverse('admin:accounts_user_change', args=[object_id])

        context = {
            **self.admin_site.each_context(request),
            'title': f'Historial - {entity_name}',
            'entries': entries,
            'back_url': back_url,
            'entity_name': entity_name,
            'object_id': object_id,
            'opts': self.model._meta,
            'original': obj,
            'breadcrumb_list_url': reverse('admin:accounts_user_changelist'),
            'breadcrumb_list_label': 'Usuarios',
        }
        if extra_context:
            context.update(extra_context)
        return TemplateResponse(request, 'admin/history/entity_history.html', context)
