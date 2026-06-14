from .base import *
from decouple import config

DEBUG = True

# Allow-all is convenient for bare local dev, but the dockerized stack sets this
# to False (via .env.docker) so CORS is restricted to the configured
# CORS_ALLOWED_ORIGINS (the frontend) instead of every origin.
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "600/minute",
    "user": "1200/minute",
}
