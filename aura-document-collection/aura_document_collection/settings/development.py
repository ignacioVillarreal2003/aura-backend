from .base import *  # noqa: F401, F403, F405

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "600/minute",
    "user": "1200/minute",
}
