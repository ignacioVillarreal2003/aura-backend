"""Dashboard admin custom view with operational KPIs."""

from datetime import timedelta
import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, connections
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from accounts.admin_parts.common import _is_admin_or_super_user
from accounts.models import User, UserRole, AuditLog, RefreshToken
from documents.models import Document
from notifications.models import Notification


logger = logging.getLogger(__name__)


def _dashboard_overview_view(request):
    """Render a lightweight admin dashboard using existing project data."""

    if not _is_admin_or_super_user(request.user):
        raise PermissionDenied

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    active_users_qs = User.objects.filter(deleted_at__isnull=True)
    users_total = active_users_qs.count()
    users_enabled = active_users_qs.filter(enabled=True).count()
    users_new_30 = active_users_qs.filter(created_at__gte=last_30_days).count()
    users_locked = active_users_qs.filter(lockout_until__gt=now).count()

    sessions_active = 0
    try:
        sessions_active = RefreshToken.objects.filter(is_revoked=False, expires_at__gt=now).count()
    except Exception:
        logger.warning('Dashboard: sessions_active unavailable.')

    logins_24h = 0
    logins_failed_24h = 0
    try:
        logins_24h = AuditLog.objects.filter(action='LOGIN', timestamp__gte=last_24h).count()
        logins_failed_24h = AuditLog.objects.filter(action='LOGIN_FAILED', timestamp__gte=last_24h).count()
    except Exception:
        logger.warning('Dashboard: login audit metrics unavailable.')

    documents_total = 0
    documents_new_30 = 0
    total_storage_bytes = 0
    documents_available = True
    try:
        document_qs = Document.objects.filter(deleted_at__isnull=True)
        documents_total = document_qs.count()
        documents_new_30 = document_qs.filter(created_at__gte=last_30_days).count()
        total_storage_bytes = document_qs.aggregate(
            total=Coalesce(Sum('file_size_bytes'), 0)
        )['total']
    except Exception:
        documents_available = False
        logger.warning('Dashboard: document metrics unavailable.')

    notification_qs = Notification.objects.filter(deleted_at__isnull=True)
    notifications_7d = 0
    notifications_read_rate_7d = 0
    notifications_unread = 0
    notifications_available = True
    try:
        notifications_7d = notification_qs.filter(created_at__gte=last_7_days).count()
        notifications_read_7d = notification_qs.filter(
            created_at__gte=last_7_days,
            status='read',
        ).count()
        notifications_unread = notification_qs.filter(status='unread').count()
        if notifications_7d:
            notifications_read_rate_7d = round((notifications_read_7d / notifications_7d) * 100, 1)
    except OperationalError:
        notifications_available = False
        logger.warning('Dashboard: notifications metrics unavailable because aura_db connection failed.')

    users_by_role = list(
        UserRole.objects.filter(deleted_at__isnull=True)
        .values('role__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )

    # Collections with most documents (replaces groups_by_user_count).
    collections_by_doc_count = []
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute("""
                SELECT dc.name, COUNT(didc.document_id) AS doc_count
                FROM document_collection dc
                LEFT JOIN document_in_document_collection didc
                    ON didc.document_collection_id = dc.id AND didc.deleted_at IS NULL
                WHERE dc.deleted_at IS NULL
                GROUP BY dc.id, dc.name
                ORDER BY doc_count DESC, dc.name
                LIMIT 8
            """)
            collections_by_doc_count = [
                {'name': row[0], 'doc_count': row[1]} for row in cursor.fetchall()
            ]
    except Exception:
        logger.warning('Dashboard: collections_by_doc_count unavailable.')

    documents_by_status = []
    largest_documents = []
    recent_documents = []
    if documents_available:
        try:
            documents_by_status = list(
                Document.objects.filter(deleted_at__isnull=True)
                .values('status')
                .annotate(total=Count('id'))
                .order_by('-total')
            )
            user_map = {u.pk: u.username for u in User.objects.only('id', 'username')}
            largest_docs_raw = list(
                Document.objects.filter(deleted_at__isnull=True)
                .values('name', 'file_size_bytes', 'created_by')
                .order_by('-file_size_bytes', 'name')[:8]
            )
            for d in largest_docs_raw:
                d['created_by_name'] = user_map.get(d['created_by'], '-')
            largest_documents = largest_docs_raw
            recent_docs_raw = list(
                Document.objects.filter(deleted_at__isnull=True)
                .values('name', 'created_at', 'created_by', 'status')
                .order_by('-created_at')[:8]
            )
            for d in recent_docs_raw:
                d['created_by_name'] = user_map.get(d['created_by'], '-')
            recent_documents = recent_docs_raw
        except Exception:
            pass

    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard Administrativo',
        'kpis': {
            'users_total': users_total,
            'users_enabled': users_enabled,
            'users_new_30': users_new_30,
            'users_locked': users_locked,
            'sessions_active': sessions_active,
            'logins_24h': logins_24h,
            'logins_failed_24h': logins_failed_24h,
            'documents_total': documents_total,
            'documents_new_30': documents_new_30,
            'notifications_7d': notifications_7d,
            'notifications_read_rate_7d': notifications_read_rate_7d,
            'notifications_unread': notifications_unread,
            'total_storage_bytes': total_storage_bytes,
            'notifications_available': notifications_available,
            'documents_available': documents_available,
        },
        'users_by_role': users_by_role,
        'collections_by_doc_count': collections_by_doc_count,
        'documents_by_status': documents_by_status,
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
