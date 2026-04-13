"""Dashboard admin custom view with operational KPIs."""

from datetime import timedelta
import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from accounts.admin_parts.common import _is_admin_or_super_user
from accounts.models import CustomGroup, User, UserRole
from documents.models import Document
from notifications.models import Notification


logger = logging.getLogger(__name__)


def _dashboard_overview_view(request):
    """Render a lightweight admin dashboard using existing project data."""

    if not _is_admin_or_super_user(request.user):
        raise PermissionDenied

    now = timezone.now()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    active_users_qs = User.objects.filter(deleted_at__isnull=True)
    document_qs = Document.objects.filter(deleted_at__isnull=True)
    notification_qs = Notification.objects.filter(deleted_at__isnull=True)

    users_total = active_users_qs.count()
    users_enabled = active_users_qs.filter(enabled=True).count()
    users_new_30 = active_users_qs.filter(created_at__gte=last_30_days).count()

    documents_total = document_qs.count()
    documents_new_30 = document_qs.filter(created_at__gte=last_30_days).count()
    documents_public = document_qs.filter(visible_to_all=True).count()
    total_storage_bytes = document_qs.aggregate(
        total=Coalesce(Sum('size_bytes'), 0)
    )['total']

    notifications_7d = 0
    notifications_read_rate_7d = 0
    notifications_available = True
    try:
        notifications_7d = notification_qs.filter(created_at__gte=last_7_days).count()
        notifications_read_7d = notification_qs.filter(
            created_at__gte=last_7_days,
            status='read',
        ).count()
        if notifications_7d:
            notifications_read_rate_7d = round((notifications_read_7d / notifications_7d) * 100, 1)
    except OperationalError:
        notifications_available = False
        logger.warning(
            'Dashboard: notifications metrics unavailable because aura_db connection failed.'
        )

    users_by_role = list(
        UserRole.objects.filter(deleted_at__isnull=True)
        .values('role__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )

    groups_by_user_count = list(
        CustomGroup.objects.filter(deleted_at__isnull=True)
        .annotate(total_users=Count('users', distinct=True))
        .values('name', 'total_users')
        .order_by('-total_users', 'name')[:8]
    )

    largest_documents = list(
        document_qs.values('name', 'size_bytes', 'created_by')
        .order_by('-size_bytes', 'name')[:8]
    )

    recent_documents = list(
        document_qs.values('name', 'created_at', 'created_by', 'visible_to_all')
        .order_by('-created_at')[:8]
    )

    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard',
        'subtitle': 'Vista general administrativa',
        'kpis': {
            'users_total': users_total,
            'users_enabled': users_enabled,
            'users_new_30': users_new_30,
            'documents_total': documents_total,
            'documents_new_30': documents_new_30,
            'documents_public': documents_public,
            'notifications_7d': notifications_7d,
            'notifications_read_rate_7d': notifications_read_rate_7d,
            'total_storage_bytes': total_storage_bytes,
            'notifications_available': notifications_available,
        },
        'users_by_role': users_by_role,
        'groups_by_user_count': groups_by_user_count,
        'largest_documents': largest_documents,
        'recent_documents': recent_documents,
        'generated_at': now,
    }
    return TemplateResponse(request, 'admin/dashboard/index.html', context)


def _custom_get_urls(self):
    urls = admin.AdminSite.get_urls(self)
    custom_urls = [
        path('dashboard/', self.admin_view(_dashboard_overview_view), name='dashboard_overview'),
    ]
    return custom_urls + urls


admin.site.get_urls = _custom_get_urls.__get__(admin.site, admin.AdminSite)
