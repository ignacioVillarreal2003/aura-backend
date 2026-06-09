"""Auth API views for login, refresh, validate, and logout."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema

import secrets
from django.conf import settings


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'
from accounts.api.serializers import (
    LoginSerializer, RefreshSerializer, LogoutSerializer,
    TokenResponseSerializer, ValidateResponseSerializer,
    ErrorResponseSerializer, LogoutResponseSerializer,
    UserDetailSerializer, UserListResponseSerializer,
    ChangePasswordSerializer,
)
from accounts.services.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    rotate_refresh_token,
    revoke_refresh_token,
    get_user_info,
    introspect_token,
)
from accounts.models import User, RefreshToken
from accounts.admin_parts.utils.audit import log_audit
from django.utils import timezone


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []
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
        tokens = issue_tokens_for_user(user, request=request)
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
    permission_classes = []

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
    permission_classes = []

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
    authentication_classes = []
    permission_classes = []

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
    authentication_classes = []
    permission_classes = []

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
        service_key = request.headers.get('X-Service-Api-Key')
        if service_key:
            expected = getattr(settings, 'SERVICE_API_KEY', '')
            if not (expected and secrets.compare_digest(service_key.strip(), str(expected))):
                return Response({'detail': 'Invalid service API key.'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return Response({'detail': 'Authorization header missing or invalid.'}, status=status.HTTP_401_UNAUTHORIZED)
            token = auth_header.split(' ', 1)[1]
            if not introspect_token(token):
                return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_401_UNAUTHORIZED)

        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'detail': 'Query parameter "q" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.db.models import Q
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
    authentication_classes = []
    permission_classes = []

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
        service_key = request.headers.get('X-Service-Api-Key')
        if service_key:
            expected = getattr(settings, 'SERVICE_API_KEY', '')
            if not (expected and secrets.compare_digest(service_key.strip(), str(expected))):
                return Response({'detail': 'Invalid service API key.'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return Response({'detail': 'Authorization header missing or invalid.'}, status=status.HTTP_401_UNAUTHORIZED)
            token = auth_header.split(' ', 1)[1]
            if not introspect_token(token):
                return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_401_UNAUTHORIZED)

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


class ChangePasswordView(APIView):
    authentication_classes = []
    permission_classes = []

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
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'detail': 'Authorization header missing or invalid.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token = auth_header.split(' ', 1)[1]
        payload = introspect_token(token)
        if not payload:
            return Response(
                {'detail': 'Invalid or expired token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = User.objects.get(pk=payload['user_id'], deleted_at__isnull=True)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

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

        # Revoke all active refresh tokens — forces re-login
        RefreshToken.objects.filter(user=user, is_revoked=False).update(is_revoked=True)

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
