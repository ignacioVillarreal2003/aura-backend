"""Configuracion del sitio admin."""

from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from apps.accounts.admin_parts.common import _is_super_admin_user, _is_admin_user, _is_effective_superadmin, has_permission


admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'

admin.site.unregister(Group)


def _custom_get_app_list(self, request, app_label=None):
    app_list = admin.AdminSite.get_app_list(self, request, app_label)

    can_view_roles = has_permission(request, 'ADMIN_ROLES_VIEW')
    can_manage_mac = has_permission(request, 'ADMIN_MAC_MANAGE')
    can_view_audit = has_permission(request, 'ADMIN_AUDIT_VIEW')
    can_view_chats = has_permission(request, 'ADMIN_CHAT_VIEW') or _is_effective_superadmin(request)
    can_view_users = has_permission(request, 'ADMIN_USERS_VIEW')

    _accounts_allowed = {'User', 'Role', 'Permission'}
    desired_order = ['User']
    if can_view_roles:
        desired_order = ['User', 'Role', 'Permission']
    order_map = {name: i for i, name in enumerate(desired_order)}

    notifications_order = ['IndividualNotification', 'GroupNotification']
    notifications_order_map = {name: i for i, name in enumerate(notifications_order)}

    placeholder_apps = [
        {
            'app_label': 'dashboard',
            'name': 'Dashboard',
            'app_url': reverse('admin:dashboard_overview'),
            'has_module_perms': True,
            'models': [
                {
                    'name': 'Vista general',
                    'object_name': 'DashboardOverview',
                    'admin_url': reverse('admin:dashboard_overview'),
                    'view_only': True,
                }
            ],
        },
    ]

    if can_manage_mac:
        grupos_models = [
            {
                'name': 'Niveles',
                'object_name': 'ClassificationLevel',
                'admin_url': reverse('admin:mac_classification_levels_list'),
                'view_only': True,
            },
            {
                'name': 'Agrupaciones',
                'object_name': 'Compartment',
                'admin_url': reverse('admin:mac_compartments_list'),
                'view_only': True,
            },
        ]
        placeholder_apps.append(
            {
                'app_label': 'grupos',
                'name': 'Grupos',
                'app_url': reverse('admin:mac_classification_levels_list'),
                'has_module_perms': True,
                'models': grupos_models,
            }
        )

    if can_view_users or can_view_audit or can_view_chats:
        gestion_models = [
            {
                'name': 'Documentos',
                'object_name': 'Document',
                'admin_url': reverse('admin:documents_document_changelist'),
                'view_only': True,
            },
        ]
        if can_view_chats:
            gestion_models.append({
                'name': 'Chats',
                'object_name': 'Chat',
                'admin_url': reverse('admin:chat_management_list'),
                'view_only': True,
            })
        if can_view_audit:
            gestion_models.append({
                'name': 'Registro de acciones',
                'object_name': 'AuditoriaList',
                'admin_url': reverse('admin:auditoria_list'),
                'view_only': True,
            })
        placeholder_apps.append(
            {
                'app_label': 'gestion',
                'name': 'Gestión',
                'app_url': reverse('admin:documents_document_changelist'),
                'has_module_perms': True,
                'models': gestion_models,
            }
        )

    app_order = {
        'dashboard': 0,
        'accounts': 1,
        'grupos': 2,
        'gestion': 3,
        'notifications': 4,
    }

    _hidden_apps = {'documents', 'chat', 'auditoria'}

    for app in app_list:
        if app.get('app_label') == 'accounts':
            allowed = _accounts_allowed if can_view_roles else {'User'}
            app['models'] = [
                m for m in app['models'] if m.get('object_name') in allowed
            ]
            app['models'].sort(
                key=lambda m: order_map.get(m.get('object_name'), len(order_map))
            )
        if app.get('app_label') == 'notifications':
            app['models'].sort(
                key=lambda m: notifications_order_map.get(m.get('object_name'), len(notifications_order_map))
            )

    app_list = [a for a in app_list if a.get('app_label') not in _hidden_apps]
    app_list = placeholder_apps[:1] + app_list + placeholder_apps[1:]
    app_list.sort(key=lambda a: app_order.get(a.get('app_label'), len(app_order)))
    return app_list


admin.site.get_app_list = _custom_get_app_list.__get__(admin.site, admin.AdminSite)
