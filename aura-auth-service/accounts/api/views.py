"""Auth API views for login, refresh, introspect, and logout."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from accounts.api.serializers import (
    LoginSerializer, RefreshSerializer, IntrospectSerializer, LogoutSerializer,
    TokenResponseSerializer, IntrospectResponseSerializer,
    ErrorResponseSerializer, LogoutResponseSerializer, MeResponseSerializer,
)
from accounts.services.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    rotate_refresh_token,
    introspect_token,
    revoke_refresh_token,
    get_user_info,
)


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
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        tokens = issue_tokens_for_user(user)
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


class IntrospectView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Introspect token',
        description='Validate an access token and return its payload (user info, roles, permissions).',
        request=IntrospectSerializer,
        responses={
            200: IntrospectResponseSerializer,
            401: ErrorResponseSerializer,
        },
        tags=['Auth'],
    )
    def post(self, request):
        serializer = IntrospectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = introspect_token(serializer.validated_data['token'])
        if not payload:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(payload, status=status.HTTP_200_OK)


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
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Get current user info',
        description='Returns the authenticated user info (id, email, roles, permissions) from the Bearer token.',
        request=None,
        responses={
            200: MeResponseSerializer,
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
