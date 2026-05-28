"""Echo message value object."""

from __future__ import annotations

from dataclasses import dataclass

from hermes_attractor.domain.exceptions import InvalidEchoError


@dataclass(frozen=True, slots=True)
class EchoMessage:
    """A validated, non-empty echo message."""

    value: str

    def __post_init__(self) -> None:
        """Validate that the message is not blank."""
        if not self.value.strip():
            msg = "Echo message must not be empty."
            raise InvalidEchoError(msg)
