"""Echo use case."""

from __future__ import annotations

from hermes_attractor.domain.echo import EchoMessage


def echo(message: str) -> EchoMessage:
    """Validate and wrap an echo message."""
    return EchoMessage(value=message)
