"""Vista del dashboard del admin con indicadores operativos."""

import concurrent.futures
import socket
from datetime import timedelta
import logging

import requests
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, connections
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from apps.accounts.admin_parts.common import has_permission
from apps.accounts.models import User, UserRole, AuditLog, RefreshToken
from apps.chat.models import Chat, ArtifactMessage
from apps.documents.models import Document
from apps.notifications.models import Notification


logger = logging.getLogger(__name__)


_HEALTH_TARGETS = (
    ('Chat', lambda: f"{settings.CHAT_SERVICE_URL.rstrip('/')}/api/v1/health"),
    ('Procesamiento de documentos', lambda: f"{settings.DOCUMENT_PROCESSING_URL.rstrip('/')}/api/v1/health"),
    ('Notificaciones', lambda: f"{settings.NOTIFICATION_SERVICE_URL.rstrip('/')}/api/v1/health"),
    ('Colección de documentos (MAC)', lambda: f"{settings.DOC_COLLECTION_SERVICE_URL.rstrip('/')}/api/v1/health"),
    ('LLM', lambda: f"{settings.LLM_SERVICE_URL.rstrip('/')}/api/v1/health"),
)

_HEALTH_BADGES = {
    'up': ('🟢', 'Operativo'),
    'degraded': ('🟡', 'Degradado'),
    'down': ('🔴', 'No disponible'),
}


def _check_one_service_health(name, url, timeout):
    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout:
        return {'name': name, 'state': 'down', 'detail': f'Sin respuesta en {timeout}s'}
    except requests.RequestException as exc:
        return {'name': name, 'state': 'down', 'detail': str(exc)}

    if response.status_code == 200:
        return {'name': name, 'state': 'up', 'detail': None}
    if response.status_code == 503:
        return {'name': name, 'state': 'degraded', 'detail': 'El servicio reporta dependencias no disponibles'}
    return {'name': name, 'state': 'degraded', 'detail': f'HTTP {response.status_code}'}


def _poll_services_health():
    """Consulta el /health de cada microservicio en paralelo. No lanza errores."""
    timeout = getattr(settings, 'SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS', 3)
    jobs = [(name, url_fn()) for name, url_fn in _HEALTH_TARGETS]

    results_by_name = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs) or 1) as executor:
            futures = {
                name: executor.submit(_check_one_service_health, name, url, timeout)
                for name, url in jobs
            }
            for name, future in futures.items():
                try:
                    results_by_name[name] = future.result(timeout=timeout + 1)
                except Exception:
                    logger.warning('Health check for %s did not complete in time.', name)
                    results_by_name[name] = {'name': name, 'state': 'down', 'detail': 'Tiempo de espera agotado'}
    except Exception:
        logger.exception('Service health poll failed unexpectedly.')

    services = []
    for name, _url in jobs:
        entry = results_by_name.get(name, {'name': name, 'state': 'down', 'detail': 'Sin datos'})
        icon, label = _HEALTH_BADGES.get(entry['state'], _HEALTH_BADGES['down'])
        services.append({**entry, 'icon': icon, 'label': label})
    return services



def _check_db_health(name: str, alias: str) -> dict:
    try:
        conn = connections[alias]
        conn.ensure_connection()
        return {'name': name, 'state': 'up', 'detail': None}
    except Exception as exc:
        return {'name': name, 'state': 'down', 'detail': str(exc)[:100]}


def _check_tcp_health(name: str, host: str, port: int, timeout: int) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return {'name': name, 'state': 'up', 'detail': None}
    except Exception as exc:
        return {'name': name, 'state': 'down', 'detail': str(exc)[:100]}


def _check_http_infra(name: str, url: str, timeout: int) -> dict:
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code < 400:
            return {'name': name, 'state': 'up', 'detail': None}
        return {'name': name, 'state': 'degraded', 'detail': f'HTTP {r.status_code}'}
    except requests.Timeout:
        return {'name': name, 'state': 'down', 'detail': f'Sin respuesta en {timeout}s'}
    except requests.RequestException as exc:
        return {'name': name, 'state': 'down', 'detail': str(exc)[:100]}


def _poll_infra_health() -> list:
    """Chequea bases de datos, cache, cola, storage y buscador. No lanza errores."""
    timeout = getattr(settings, 'SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS', 3)

    jobs = [
        ('BD Auth',       lambda: _check_db_health('BD Auth', 'default')),
        ('BD Principal',  lambda: _check_db_health('BD Principal', 'aura_db')),
        ('Redis',         lambda: _check_tcp_health('Redis', 'memory_db', 6379, timeout)),
        ('RabbitMQ',      lambda: _check_tcp_health('RabbitMQ', 'queue', 5672, timeout)),
        ('MinIO',         lambda: _check_http_infra('MinIO', 'http://storage:9000/minio/health/live', timeout)),
        ('Neo4j',         lambda: _check_http_infra('Neo4j', 'http://neo4j:7474', timeout)),
    ]

    results_by_name = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            futures = {name: executor.submit(fn) for name, fn in jobs}
            for name, future in futures.items():
                try:
                    results_by_name[name] = future.result(timeout=timeout + 1)
                except Exception:
                    results_by_name[name] = {'name': name, 'state': 'down', 'detail': 'Tiempo de espera agotado'}
    except Exception:
        logger.exception('Infra health poll failed unexpectedly.')

    result = []
    for name, _fn in jobs:
        entry = results_by_name.get(name, {'name': name, 'state': 'down', 'detail': 'Sin datos'})
        icon, label = _HEALTH_BADGES.get(entry['state'], _HEALTH_BADGES['down'])
        result.append({**entry, 'icon': icon, 'label': label})
    return result



def _get_graph_stats(user) -> dict:
    """Estadisticas del grafo via document-processing. No lanza errores."""
    try:
        from apps.documents.services.document_processing_client import get_graph_stats
        data = get_graph_stats(user) or {}
        return {
            'node_count': data.get('total_entities', 0),
            'rel_count': data.get('total_relations', 0),
            'docs_indexed': data.get('total_documents_indexed', 0),
            'available': True,
        }
    except Exception:
        logger.warning('Dashboard: graph stats unavailable via document-processing.')
        return {'node_count': 0, 'rel_count': 0, 'docs_indexed': 0, 'available': False}


def _dashboard_overview_view(request):
    """Arma el dashboard del admin con datos del proyecto."""

    if not has_permission(request, 'ADMIN_DASHBOARD_VIEW'):
        raise PermissionDenied

    services_health = _poll_services_health()
    infra_health = _poll_infra_health()

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    active_users_qs = User.objects.filter(deleted_at__isnull=True)

    try:
        elevated_user_ids = set(
            UserRole.objects.filter(
                role__name__in=['admin', 'superadmin'],
                deleted_at__isnull=True,
            ).values_list('user_id', flat=True)
        )
    except Exception:
        elevated_user_ids = set()
        logger.warning('Dashboard: could not determine elevated user IDs.')

    regular_users_qs = active_users_qs.exclude(pk__in=elevated_user_ids)
    users_regular = regular_users_qs.count()
    users_regular_new_30 = regular_users_qs.filter(created_at__gte=last_30_days).count()

    users_locked = active_users_qs.filter(lockout_until__gt=now).count()

    users_inactive_30d = 0
    try:
        users_inactive_30d = active_users_qs.filter(
            created_at__lt=last_30_days,
        ).filter(
            Q(last_login__isnull=True) | Q(last_login__lt=last_30_days)
        ).count()
    except Exception:
        logger.warning('Dashboard: users_inactive_30d unavailable.')

    active_users_24h = 0
    try:
        active_users_24h = (
            AuditLog.objects.filter(action='LOGIN', timestamp__gte=last_24h, actor_id__isnull=False)
            .values('actor_id').distinct().count()
        )
    except Exception:
        logger.warning('Dashboard: active_users_24h unavailable.')

    locked_users_list = []
    try:
        locked_users_list = list(
            active_users_qs.filter(lockout_until__gt=now)
            .values('username', 'email', 'lockout_until', 'failed_login_attempts')
            .order_by('lockout_until')[:20]
        )
    except Exception:
        logger.warning('Dashboard: locked_users_list unavailable.')

    sessions_active = 0
    active_sessions_list = []
    try:
        sessions_active = RefreshToken.objects.filter(is_revoked=False, expires_at__gt=now).count()
        active_sessions_list = list(
            RefreshToken.objects.filter(is_revoked=False, expires_at__gt=now)
            .values('user__username', 'user__email')
            .annotate(last_login=Max('created_at'), session_count=Count('id'))
            .order_by('-last_login')[:20]
        )
    except Exception:
        logger.warning('Dashboard: sessions_active unavailable.')

    logins_24h = 0
    logins_failed_24h = 0
    suspicious_users = []
    try:
        logins_24h = AuditLog.objects.filter(action='LOGIN', timestamp__gte=last_24h).count()
        logins_failed_24h = AuditLog.objects.filter(action='LOGIN_FAILED', timestamp__gte=last_24h).count()
        suspicious_users = list(
            AuditLog.objects.filter(
                action='LOGIN_FAILED',
                timestamp__gte=last_24h,
                actor_username__isnull=False,
            )
            .values('actor_username')
            .annotate(failed_count=Count('id'))
            .order_by('-failed_count')[:5]
        )
    except Exception:
        logger.warning('Dashboard: login audit metrics unavailable.')

    chats_total = 0
    chats_active_24h = 0
    messages_7d = 0
    chat_available = True
    try:
        chats_total = Chat.objects.filter(deleted_at__isnull=True).count()
        chats_active_24h = Chat.objects.filter(
            deleted_at__isnull=True,
            last_message_at__gte=last_24h,
        ).count()
        messages_7d = ArtifactMessage.objects.filter(
            deleted_at__isnull=True,
            created_at__gte=last_7_days,
            sender_type='user',
        ).count()
    except Exception:
        chat_available = False
        logger.warning('Dashboard: chat metrics unavailable.')

    documents_total = 0
    documents_failed = 0
    total_storage_bytes = 0
    documents_available = True
    try:
        document_qs = Document.objects.filter(deleted_at__isnull=True)
        documents_total = document_qs.count()
        documents_failed = document_qs.filter(status='failed').count()
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
            created_at__gte=last_7_days, status='read',
        ).count()
        notifications_unread = notification_qs.filter(status='unread').count()
        if notifications_7d:
            notifications_read_rate_7d = round((notifications_read_7d / notifications_7d) * 100, 1)
    except OperationalError:
        notifications_available = False
        logger.warning('Dashboard: notifications metrics unavailable because aura_db connection failed.')

    neo4j_stats = _get_graph_stats(request.user)

    users_by_role = list(
        UserRole.objects.filter(deleted_at__isnull=True)
        .values('role__name')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )

    levels_by_doc_count = []
    compartments_by_doc_count = []
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute("""
                SELECT cl.name, cl.rank, COUNT(DISTINCT didc.document_id) AS doc_count
                FROM classification_level cl
                LEFT JOIN document_collection dc
                    ON dc.classification_level_id = cl.id AND dc.deleted_at IS NULL
                LEFT JOIN document_in_document_collection didc
                    ON didc.document_collection_id = dc.id AND didc.deleted_at IS NULL
                GROUP BY cl.id, cl.name, cl.rank
                ORDER BY doc_count DESC, cl.rank DESC
            """)
            levels_by_doc_count = [
                {'name': row[0], 'rank': row[1], 'doc_count': row[2]}
                for row in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT comp.name, COUNT(DISTINCT didc.document_id) AS doc_count
                FROM compartment comp
                LEFT JOIN document_collection_compartment dcc
                    ON dcc.compartment_id = comp.id
                LEFT JOIN document_in_document_collection didc
                    ON didc.document_collection_id = dcc.document_collection_id
                    AND didc.deleted_at IS NULL
                GROUP BY comp.id, comp.name
                ORDER BY doc_count DESC, comp.name
            """)
            compartments_by_doc_count = [
                {'name': row[0], 'doc_count': row[1]}
                for row in cursor.fetchall()
            ]
    except Exception:
        logger.warning('Dashboard: levels/compartments_by_doc_count unavailable.')

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
            largest_docs_raw = list(
                Document.objects.filter(deleted_at__isnull=True)
                .values('name', 'file_size_bytes', 'created_by')
                .order_by('-file_size_bytes', 'name')[:8]
            )
            recent_docs_raw = list(
                Document.objects.filter(deleted_at__isnull=True)
                .values('name', 'created_at', 'created_by', 'status')
                .order_by('-created_at')[:8]
            )
            referenced_ids = {d['created_by'] for d in largest_docs_raw} | {d['created_by'] for d in recent_docs_raw}
            user_map = {
                u.pk: u.username
                for u in User.objects.only('id', 'username').filter(pk__in=referenced_ids)
            }
            for d in largest_docs_raw:
                d['created_by_name'] = user_map.get(d['created_by'], '-')
            for d in recent_docs_raw:
                d['created_by_name'] = user_map.get(d['created_by'], '-')
            largest_documents = largest_docs_raw
            recent_documents = recent_docs_raw
        except Exception:
            pass

    context = {
        **admin.site.each_context(request),
        'title': 'Dashboard Administrativo',
        'services_health': services_health,
        'infra_health': infra_health,
        'kpis': {
            'users_regular': users_regular,
            'users_regular_new_30': users_regular_new_30,
            'users_locked': users_locked,
            'users_inactive_30d': users_inactive_30d,
            'active_users_24h': active_users_24h,
            'sessions_active': sessions_active,
            'logins_24h': logins_24h,
            'logins_failed_24h': logins_failed_24h,
            'chats_total': chats_total,
            'chats_active_24h': chats_active_24h,
            'messages_7d': messages_7d,
            'chat_available': chat_available,
            'documents_total': documents_total,
            'documents_failed': documents_failed,
            'notifications_7d': notifications_7d,
            'notifications_read_rate_7d': notifications_read_rate_7d,
            'notifications_unread': notifications_unread,
            'total_storage_bytes': total_storage_bytes,
            'notifications_available': notifications_available,
            'documents_available': documents_available,
        },
        'neo4j_stats': neo4j_stats,
        'locked_users_list': locked_users_list,
        'active_sessions_list': active_sessions_list,
        'suspicious_users': suspicious_users,
        'users_by_role': users_by_role,
        'levels_by_doc_count': levels_by_doc_count,
        'compartments_by_doc_count': compartments_by_doc_count,
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
