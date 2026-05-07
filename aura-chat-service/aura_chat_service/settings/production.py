from .base import *
from decouple import config

DEBUG = False

SECRET_KEY = config("SECRET_KEY")
SERVICE_API_KEY = config("SERVICE_API_KEY")

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CORS_ALLOW_ALL_ORIGINS = False

LOGGING["loggers"]["apps"]["level"] = "INFO"
LOGGING["loggers"]["core"]["level"] = "INFO"
