from .base import *

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "600/minute",
    "user": "1200/minute",
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL", default="redis://localhost:6379/0")],
        },
    },
}
