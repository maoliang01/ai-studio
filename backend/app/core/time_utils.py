"""Application time helpers.

Database timestamps remain naive UTC for compatibility. User-facing schedule
times are converted to Asia/Shanghai at the API boundary.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def local_to_utc_naive(value: datetime) -> datetime:
    aware = value.replace(tzinfo=BEIJING_TZ) if value.tzinfo is None else value.astimezone(BEIJING_TZ)
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def utc_naive_to_beijing(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(BEIJING_TZ)


def beijing_iso(value: datetime | None) -> str | None:
    converted = utc_naive_to_beijing(value)
    return converted.isoformat() if converted else None
