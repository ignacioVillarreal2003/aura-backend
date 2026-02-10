"""Admin site configuration."""

from django.contrib import admin
from django.contrib.auth.models import Group
from accounts.admin_parts.common import _is_super_admin_user


# Customize admin site
admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'

# Unregister Group from Django auth
admin.site.unregister(Group)


def _custom_get_app_list(self, request):
    app_list = admin.AdminSite.get_app_list(self, request)
    desired_order = ['User', 'UserRole']
    if _is_super_admin_user(request.user):
        desired_order = [
            'User',
            'CustomGroup',
            'Role',
            'UserRole',
            'Permission',
            'PermissionInRole',
        ]
    order_map = {name: index for index, name in enumerate(desired_order)}

    documents_order = ['Document', 'DocumentRole']
    documents_order_map = {name: index for index, name in enumerate(documents_order)}

    app_order = {
        'accounts': 0,
        'documents': 1,
    }

    for app in app_list:
        if app.get('app_label') == 'accounts':
            if not _is_super_admin_user(request.user):
                app['models'] = [
                    model for model in app['models']
                    if model.get('object_name') in {'User', 'UserRole'}
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
    app_list.sort(
        key=lambda app: app_order.get(app.get('app_label'), len(app_order))
    )
    return app_list


admin.site.get_app_list = _custom_get_app_list.__get__(admin.site, admin.AdminSite)
