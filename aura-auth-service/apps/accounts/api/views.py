"""Vistas de la API de autenticacion: login, refresh, validate y logout."""

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import LoginRateThrottle, ScopedRedisThrottle
from apps.accounts.admin_parts.utils.audit import log_audit
from apps.accounts.api.serializers import (
    ChangePasswordSerializer,
    ErrorResponseSerializer,
    LoginSerializer,
    LogoutResponseSerializer,
    LogoutSerializer,
    RefreshSerializer,
    TokenResponseSerializer,
    UserListResponseSerializer,
    ValidateResponseSerializer,
)
from apps.accounts.api.permissions import IsServiceOrUserViewer, can_view_user_directory
from apps.accounts.authentication import JWTAuthentication
from apps.accounts.models import RefreshToken, User
from apps.accounts.services.auth_service import (
    authenticate_user,
    get_user_info,
    issue_tokens_for_user,
    revoke_all_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
)
from apps.notifications.services.notification_client import emit_event_async


def _is_new_device_login(user, request) -> bool:
    """Es un dispositivo nuevo si nunca hubo un refresh token con ese user agent."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if not user_agent:
        return False
    return not RefreshToken.objects.filter(user=user, user_agent=user_agent).exists()


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        summary='Login',
        description='Authenticate with username and password, returns access and refresh tokens.',
        request=LoginSerializer,
        responses={
            200: TokenResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_user(
            serializer.validated_data['username'],
            serializer.validated_data['password'],
        )
        if not user:
            log_audit(
                actor=None,
                action='LOGIN_FAILED',
                entity_type='auth_user',
                entity_label=serializer.validated_data.get('username'),
                details={'reason': 'Invalid credentials'},
                source='api',
            )
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        is_new_device = _is_new_device_login(user, request)
        tokens = issue_tokens_for_user(user, request=request)
        if is_new_device:
            emit_event_async(
                event_type='auth.new_login',
                recipient_ids=[user.pk],
                context={
                    'location': request.META.get('REMOTE_ADDR') or '',
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
                    'recipient_email': user.email,
                    'recipient_name': user.username,
                },
            )
        log_audit(
            actor=user,
            action='LOGIN',
            entity_type='auth_user',
            entity_id=user.pk,
            entity_label=user.username,
            source='api',
        )
        return Response(tokens, status=status.HTTP_200_OK)


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRedisThrottle]
    throttle_scope = 'refresh'

    @extend_schema(
        summary='Refresh token',
        description='Exchange a valid refresh token for a new access and refresh token pair.',
        request=RefreshSerializer,
        responses={
            200: TokenResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = rotate_refresh_token(serializer.validated_data['refresh_token'], request=request)
        if not tokens:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Logout',
        description='Revoke a refresh token, invalidating the session.',
        request=LogoutSerializer,
        responses={
            200: LogoutResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoked = revoke_refresh_token(serializer.validated_data['refresh_token'])
        if not revoked:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        log_audit(
            actor=None,
            action='LOGOUT',
            entity_type='auth_user',
            source='api',
        )
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


class ValidateView(APIView):
    # Abierto a proposito: este es el endpoint que valida el token de la peticion
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Validate token',
        description='Validate a Bearer token and return user info (id, email, username, roles, permissions).',
        request=None,
        responses={
            200: ValidateResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def get(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response({'detail': 'Authorization header missing or invalid.'}, status=status.HTTP_401_UNAUTHORIZED)
        token = auth_header.split(' ', 1)[1]
        user_info = get_user_info(token)
        if not user_info:
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(user_info, status=status.HTTP_200_OK)


class UserLookupView(APIView):
    permission_classes = [IsServiceOrUserViewer]
    throttle_classes = [ScopedRedisThrottle]
    throttle_scope = 'user_lookup'

    @extend_schema(
        summary='Lookup users',
        description=(
            'Search active users by a single free-text query (`q`). '
            'Matches partially (case-insensitive) against name, username, and email. '
            'Requires either a valid Bearer token (end-user) or a valid X-Service-Api-Key header '
            '(service-to-service).'
        ),
        parameters=[
            {'name': 'q', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
        ],
        responses={
            200: UserListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'detail': 'Query parameter "q" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        users = User.objects.filter(deleted_at__isnull=True, status='active').filter(
            Q(name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q)
        )

        results = [
            {
                'id':       u.id,
                'username': u.username,
                'name':     u.name,
                'email':    u.email,
            }
            for u in users
        ]
        return Response({'count': len(results), 'results': results}, status=status.HTTP_200_OK)


class UsersByIdsView(APIView):
    throttle_classes = [ScopedRedisThrottle]
    throttle_scope = 'user_lookup'

    @extend_schema(
        summary='Get users by IDs',
        description=(
            'Fetch basic profile data for a list of user IDs. '
            'Accepts `ids` as a comma-separated query param. '
            'Requires either a valid Bearer token or X-Service-Api-Key header.'
        ),
        parameters=[
            {'name': 'ids', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
        ],
        responses={
            200: UserListResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def get(self, request):
        ids_param = request.query_params.get('ids', '').strip()
        if not ids_param:
            return Response({'detail': 'Query parameter "ids" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ids = [int(i.strip()) for i in ids_param.split(',') if i.strip()]
        except ValueError:
            return Response({'detail': '"ids" must be a comma-separated list of integers.'}, status=status.HTTP_400_BAD_REQUEST)

        if not ids:
            return Response({'count': 0, 'results': []}, status=status.HTTP_200_OK)

        users = User.objects.filter(pk__in=ids, deleted_at__isnull=True)
        include_email = can_view_user_directory(request.user)
        results = [
            {
                'id':       u.id,
                'username': u.username,
                'name':     u.name,
                **({'email': u.email} if include_email else {}),
            }
            for u in users
        ]
        return Response({'count': len(results), 'results': results}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRedisThrottle]
    throttle_scope = 'change_password'

    @extend_schema(
        summary='Change password',
        description=(
            'Change the authenticated user\'s password. '
            'Requires a valid Bearer token. '
            'All active refresh tokens are revoked after a successful change, '
            'forcing a new login.'
        ),
        request=ChangePasswordSerializer,
        responses={
            200: LogoutResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def post(self, request):
        user = request.user

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'detail': 'La contraseña actual es incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.last_password_change = timezone.now()
        user.save(update_fields=['password', 'last_password_change'])

        revoke_all_sessions(user)

        emit_event_async(
            event_type='auth.password.changed',
            recipient_ids=[user.pk],
            context={
                'at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
                'recipient_email': user.email,
                'recipient_name': user.username,
            },
        )

        log_audit(
            actor=user,
            action='UPDATE',
            entity_type='auth_user',
            entity_id=user.pk,
            entity_label=user.username,
            details={'changed_fields': ['password']},
            source='api',
        )

        return Response({'detail': 'Contraseña actualizada correctamente.'}, status=status.HTTP_200_OK)
