"""Unit tests for the HealthReport value object."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_attractor.domain.health import HealthReport

pytestmark = pytest.mark.unit


def test_to_dict_serializes_fields() -> None:
    """to_dict returns the status, version, and ISO-formatted timestamp."""
    moment = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
    report = HealthReport(status="ok", version="1.2.3", checked_at=moment)
    assert report.to_dict() == {
        "status": "ok",
        "version": "1.2.3",
        "checked_at": moment.isoformat(),
    }
