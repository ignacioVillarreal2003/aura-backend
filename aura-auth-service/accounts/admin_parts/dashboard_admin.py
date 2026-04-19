"""Dashboard admin custom view with operational KPIs."""

from datetime import timedelta
import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, connections
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.utils import timezone

from accounts.admin_parts.common import is_admin_or_super_user
from accounts.models import CustomGroup, User, UserRole
from documents.models import Document
from notifications.models import Notification


logger = logging.getLogger(__name__)


def _dashboard_overview_view(request):
    """Render a lightweight admin dashboard using existing project data."""

    if not is_admin_or_super_user(request.user):
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

    # auth_user_custom_groups lives in aura_db (cross-DB); cannot use ORM annotation.
    # Fetch member counts via raw SQL then merge with group names from auth_db.
    groups_by_user_count = []
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT customgroup_id::text, COUNT(DISTINCT user_id) AS total_users
                FROM auth_user_custom_groups
                GROUP BY customgroup_id
                """
            )
            counts = {row[0]: row[1] for row in cursor.fetchall()}

        groups_qs = CustomGroup.objects.filter(deleted_at__isnull=True).values('id', 'name')
        merged = [
            {'name': g['name'], 'total_users': counts.get(str(g['id']), 0)}
            for g in groups_qs
        ]
        groups_by_user_count = sorted(
            merged, key=lambda x: (-x['total_users'], x['name'])
        )[:8]
    except Exception:
        logger.warning('Dashboard: groups_by_user_count unavailable (cross-DB query failed)')

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
