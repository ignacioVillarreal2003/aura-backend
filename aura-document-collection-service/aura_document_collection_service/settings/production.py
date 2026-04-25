from decouple import Csv, config

from .base import *

DEBUG = False

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CORS_ALLOW_ALL_ORIGINS = False
_cors_prod = config("CORS_ORIGINS", default="").strip()
if _cors_prod in ("*", '["*"]', "['*']"):
    CORS_ALLOWED_ORIGINS = list(
        config(
            "CORS_ALLOWED_ORIGINS",
            default=",".join(DEFAULT_LOCAL_CORS_ORIGINS),
            cast=Csv(),
        )
    )
elif not _cors_prod:
    CORS_ALLOWED_ORIGINS = list(DEFAULT_LOCAL_CORS_ORIGINS)
else:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_prod.split(",") if o.strip()]

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": config("THROTTLE_ANON_RATE", default="20/minute"),
    "user": config("THROTTLE_USER_RATE", default="60/minute"),
}

LOGGING["loggers"]["apps"]["level"] = "INFO"
LOGGING["loggers"]["core"]["level"] = "INFO"
