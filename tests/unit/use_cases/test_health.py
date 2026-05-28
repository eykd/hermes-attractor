"""Unit tests for the health-check use case."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_attractor.use_cases.health import check_health

pytestmark = pytest.mark.unit


class _FixedClock:
    """A test double Clock that always returns a fixed moment."""

    def __init__(self, moment: datetime) -> None:
        """Store the fixed moment to return from now()."""
        super().__init__()
        self._moment = moment

    def now(self) -> datetime:
        """Return the stored fixed moment."""
        return self._moment


def test_check_health_stamps_clock_time() -> None:
    """check_health returns an ok report stamped with the clock's time."""
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    report = check_health(clock=_FixedClock(moment), version="9.9.9")
    assert report.status == "ok"
    assert report.version == "9.9.9"
    assert report.checked_at == moment
