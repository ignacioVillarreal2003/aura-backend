from .base import *

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "anon": "600/minute",
    "user": "1200/minute",
})
