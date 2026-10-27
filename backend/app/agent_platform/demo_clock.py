"""Mutable demo business date; security lifetimes keep their real clocks."""

from datetime import datetime, timedelta, timezone


BEIJING = timezone(timedelta(hours=8))


class DemoClock:
    def __init__(self) -> None:
        self._at: datetime | None = None

    def __call__(self) -> datetime:
        return self._at if self._at is not None else datetime.now(BEIJING)

    def set(self, at: datetime) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("INVALID_ARGUMENT")
        self._at = at.astimezone(BEIJING)
