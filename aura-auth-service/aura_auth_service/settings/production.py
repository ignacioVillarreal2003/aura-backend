"""Production settings — security hardened. DEBUG is off."""

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = False

# In production the JWT signing key MUST be set explicitly — never silently fall
# back to SECRET_KEY (see base.py).
if not config('JWT_SIGNING_KEY', default=None):
    raise ImproperlyConfigured('JWT_SIGNING_KEY must be set in production.')

# Security hardening. SECURE_SSL_REDIRECT is configurable so a rollout can keep
# the HTTPS redirect OFF until TLS termination is actually in place (avoids a
# redirect loop / lockout). The gateway already forwards X-Forwarded-Proto, and
# SECURE_PROXY_SSL_HEADER is set in base.py.
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=True, cast=bool)
