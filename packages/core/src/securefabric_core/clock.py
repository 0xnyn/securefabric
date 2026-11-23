"""An injectable clock. Everything that reads time takes one (part 9, section 4)."""

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """A clock tests move by hand, so retry schedules run in milliseconds."""

    def __init__(self, at: datetime | None = None) -> None:
        self._at = at or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = at

    def advance(self, seconds: float = 0, **kwargs: float) -> datetime:
        self._at += timedelta(seconds=seconds, **kwargs)
        return self._at


SYSTEM_CLOCK = SystemClock()


def utcnow() -> datetime:
    return datetime.now(UTC)
