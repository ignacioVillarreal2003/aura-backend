from .base import *
from decouple import config

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "600/minute",
    "user": "1200/minute",
}
