"""Auth API views for login, refresh, validate, and logout."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from accounts.api.serializers import (
    LoginSerializer, RefreshSerializer, LogoutSerializer,
    TokenResponseSerializer, ValidateResponseSerializer,
    ErrorResponseSerializer, LogoutResponseSerializer,
    UserLookupRequestSerializer, UserLookupItemSerializer,
)
from accounts.models import User
from accounts.authentication import ServiceKeyAuthentication, JWTAuthentication
from accounts.services.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    rotate_refresh_token,
    revoke_refresh_token,
    get_user_info,
)
from accounts.services.audit_service import log_audit


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

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
        tokens = issue_tokens_for_user(user)
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
        tokens = rotate_refresh_token(serializer.validated_data['refresh_token'])
        if not tokens:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):

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


class UserBulkLookupView(APIView):
    authentication_classes = [ServiceKeyAuthentication, JWTAuthentication]

    @extend_schema(
        summary='Bulk user lookup',
        description='Given a list of user IDs, returns id, username and email for each found user.',
        request=UserLookupRequestSerializer,
        responses={200: UserLookupItemSerializer(many=True), 400: ErrorResponseSerializer},
        tags=['Users'],
    )
    def post(self, request):
        serializer = UserLookupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data['ids']
        users = (
            User.objects
            .filter(pk__in=ids, deleted_at__isnull=True)
            .values('id', 'username', 'email')
        )
        return Response(list(users), status=status.HTTP_200_OK)
