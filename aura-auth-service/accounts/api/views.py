"""Auth API views for login, refresh, introspect, and logout."""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.api.serializers import LoginSerializer, RefreshSerializer, IntrospectSerializer, LogoutSerializer
from accounts.services.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    rotate_refresh_token,
    introspect_token,
    revoke_refresh_token,
)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

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

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoked = revoke_refresh_token(serializer.validated_data['refresh_token'])
        if not revoked:
            return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)
