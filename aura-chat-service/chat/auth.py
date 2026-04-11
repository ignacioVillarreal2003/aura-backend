import logging
from jose import jwt, JWTError
from rest_framework.authentication import BaseAuthentication

logger = logging.getLogger(__name__)


class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.is_authenticated = True

    def __str__(self):
        return f'User({self.id})'


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        from django.conf import settings

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            request.bearer_token = 'user_token_123'
            return (MockUser(1), None)

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get('user_id') or int(payload.get('sub', 1))
            request.bearer_token = token
            return (MockUser(user_id), token)
        except JWTError:
            logger.debug('Invalid JWT, falling back to user_id=1')
            request.bearer_token = 'user_token_123'
            return (MockUser(1), None)
