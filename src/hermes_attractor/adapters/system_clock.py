"""System clock adapter backed by the standard library."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """A Clock implementation using the system wall clock in UTC."""

    def now(self) -> datetime:
        """Return the current UTC time as a timezone-aware datetime."""
        return datetime.now(UTC)
