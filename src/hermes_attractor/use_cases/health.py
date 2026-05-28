"""Health-check use case."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes_attractor.domain.health import HealthReport

if TYPE_CHECKING:
    from hermes_attractor.ports.clock import Clock


def check_health(*, clock: Clock, version: str) -> HealthReport:
    """Produce a HealthReport stamped with the clock's current time."""
    return HealthReport(status="ok", version=version, checked_at=clock.now())
