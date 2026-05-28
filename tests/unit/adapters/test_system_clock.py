"""Unit tests for the SystemClock adapter."""

from __future__ import annotations

from datetime import timedelta

import pytest

from hermes_attractor.adapters.system_clock import SystemClock

pytestmark = pytest.mark.unit


def test_now_returns_timezone_aware_utc() -> None:
    """SystemClock.now returns a timezone-aware UTC datetime."""
    moment = SystemClock().now()
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)
