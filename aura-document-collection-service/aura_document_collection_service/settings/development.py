from .base import *

DEBUG = True

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "600/minute",
    "user": "1200/minute",
}
