"""Health report value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Immutable snapshot of plugin health at a point in time."""

    status: str
    version: str
    checked_at: datetime

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the report."""
        return {
            "status": self.status,
            "version": self.version,
            "checked_at": self.checked_at.isoformat(),
        }
