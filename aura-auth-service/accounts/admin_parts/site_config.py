"""Admin site configuration."""

from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from accounts.admin_parts.common import _is_super_admin_user, _is_admin_user


# Customize admin site
admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'

# Unregister Group from Django auth
admin.site.unregister(Group)


def _custom_get_app_list(self, request, app_label=None):
    app_list = admin.AdminSite.get_app_list(self, request, app_label)
    desired_order = ['User']
    if _is_super_admin_user(request.user) or _is_admin_user(request.user):
        desired_order = [
            'User',
            'CustomGroup',
            'Role',
            'FauRole',
            'Permission',
        ]
    order_map = {name: index for index, name in enumerate(desired_order)}

    documents_order = ['Document']
    documents_order_map = {name: index for index, name in enumerate(documents_order)}

    notifications_order = ['IndividualNotification', 'GroupNotification', 'SystemNotification']
    notifications_order_map = {name: index for index, name in enumerate(notifications_order)}

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
        # 'chat' is now a real registered app — no placeholder needed.
        # 'notifications' placeholder removed — real models registered via notifications app.
    ]

    if _is_super_admin_user(request.user):
        placeholder_apps.append(
            {
                'app_label': 'auditoria',
                'name': 'Auditoría',
                'app_url': reverse('admin:auditoria_list'),
                'has_module_perms': True,
                'models': [
                    {
                        'name': 'Registro de acciones',
                        'object_name': 'AuditoriaList',
                        'admin_url': reverse('admin:auditoria_list'),
                        'view_only': True,
                    }
                ],
            }
        )

    app_order = {
        'dashboard': 0,
        'accounts': 1,
        'documents': 2,
        'chat': 3,
        'notifications': 4,
        'auditoria': 5,
    }

    for app in app_list:
        if app.get('app_label') == 'accounts':
            if not (_is_super_admin_user(request.user) or _is_admin_user(request.user)):
                app['models'] = [
                    model for model in app['models']
                    if model.get('object_name') in {'User'}
                ]
            app['models'].sort(
                key=lambda model: order_map.get(model.get('object_name'), len(order_map))
            )
        if app.get('app_label') == 'documents':
            app['models'].sort(
                key=lambda model: documents_order_map.get(
                    model.get('object_name'),
                    len(documents_order_map)
                )
            )
        if app.get('app_label') == 'notifications':
            app['models'].sort(
                key=lambda model: notifications_order_map.get(
                    model.get('object_name'),
                    len(notifications_order_map)
                )
            )
    # placeholder_apps[0] = Dashboard (always first).
    # placeholder_apps[1:] = Auditoría (super-admin only, appended above).
    # Real apps (accounts, documents, chat, notifications) come from app_list.
    app_list = placeholder_apps[:1] + app_list + placeholder_apps[1:]
    app_list.sort(
        key=lambda app: app_order.get(app.get('app_label'), len(app_order))
    )
    return app_list


admin.site.get_app_list = _custom_get_app_list.__get__(admin.site, admin.AdminSite)
