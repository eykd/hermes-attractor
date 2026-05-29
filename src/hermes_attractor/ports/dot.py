"""DotSerializer port: DOT (de)serialization Protocol.

This port isolates pydot from the domain. Only adapters implement this Protocol.

See: specs/001-attractor-kanban/contracts/ports.md §DotSerializer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hermes_attractor.domain.pipeline import Pipeline


class DotSerializer(Protocol):
    """Port for DOT format (de)serialization of pipelines (FR-001, FR-002, R-DOT).

    Implementations (adapters) own the pydot dependency and the Attractor
    attribute name mapping. The domain never imports pydot.
    """

    def parse(self, dot: str) -> Pipeline:
        """Parse a DOT string into a Pipeline aggregate.

        Args:
            dot: A Graphviz DOT string.

        Returns:
            A Pipeline populated from the DOT definition.

        Raises:
            PipelineValidationError: If the input is malformed, exceeds resource
                limits, or contains unknown/invalid Attractor attributes.
        """
        ...

    def emit(self, pipeline: Pipeline) -> str:
        """Serialize a Pipeline aggregate to a DOT string.

        Args:
            pipeline: The pipeline to serialize.

        Returns:
            A valid Graphviz DOT string representation of the pipeline.
        """
        ...
