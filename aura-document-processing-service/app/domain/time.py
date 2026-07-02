from datetime import datetime, timedelta, timezone
from typing import Final

APP_TIMEZONE: Final[timezone] = timezone(timedelta(hours=-3))


def now() -> datetime:
    return datetime.now(APP_TIMEZONE)
