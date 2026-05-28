"""Clock port: the time source the application depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """Provides the current time."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime."""
        ...
