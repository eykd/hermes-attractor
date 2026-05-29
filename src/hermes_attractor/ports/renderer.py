"""Renderer port: human-readable pipeline summary.

See: specs/001-attractor-kanban/contracts/ports.md §Renderer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hermes_attractor.domain.pipeline import Pipeline


class Renderer(Protocol):
    """Port for rendering a human-readable summary of a Pipeline (FR-005).

    The pure-Python text summary adapter requires no Graphviz binary.
    Image rendering (if needed) is optional and runtime-detected.
    """

    def summarize(self, pipeline: Pipeline) -> str:
        """Return a human-readable text summary of the pipeline.

        Args:
            pipeline: The pipeline to summarize.

        Returns:
            A multi-line string suitable for display in a terminal or LLM context.
        """
        ...
