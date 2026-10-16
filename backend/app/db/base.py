import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware DateTime that round-trips correctly on SQLite, which has
    no native tz-aware storage and silently drops tzinfo on read-back --
    without this, a value written as UTC comes back naive, gets serialized to
    JSON without a timezone marker, and browsers then parse it as local time
    (e.g. `new Date("2026-01-01T12:00:00")` is read as noon *local*, not UTC).
    On Postgres (TIMESTAMPTZ round-trips correctly natively) this is a no-op.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name != "sqlite":
            return value
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is None or dialect.name != "sqlite":
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
