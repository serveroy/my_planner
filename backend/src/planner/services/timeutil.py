from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from planner.db.models import User


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def local_now(user: User, now_utc: datetime | None = None) -> datetime:
    """The user's wall-clock time as a naive datetime."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(user_tz(user)).replace(tzinfo=None)


def local_today(user: User, now_utc: datetime | None = None) -> date:
    return local_now(user, now_utc).date()


def parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)
