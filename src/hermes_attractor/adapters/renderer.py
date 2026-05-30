"""Pure-Python pipeline text renderer (no Graphviz binary required).

See: specs/001-attractor-kanban/contracts/ports.md §Renderer
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_attractor.domain.pipeline import Pipeline

#: Maximum prompt characters to include in summary snippet.
_PROMPT_SNIPPET_LEN: int = 40


class TextRenderer:
    """Pure-Python renderer that produces a plain-text pipeline summary.

    Requires no Graphviz binary. Image rendering is not provided by this adapter.
    """

    def summarize(self, pipeline: Pipeline) -> str:
        """Return a human-readable text summary of the pipeline.

        Lists the pipeline spec_id, each node (id, shape, optional profile/prompt),
        and each edge (source -> target, optional condition/label).

        Args:
            pipeline: The pipeline to summarize.

        Returns:
            A multi-line string suitable for terminal or LLM display.
        """
        lines: list[str] = [
            f"Pipeline: {pipeline.spec_id}",
            f"  Nodes: {len(pipeline.nodes)}",
            f"  Edges: {len(pipeline.edges)}",
            "",
            "Nodes:",
        ]
        for node in pipeline.nodes:
            parts = [f"  {node.node_id} ({node.shape.name})"]
            if node.profile is not None:
                parts.append(f"profile={node.profile!r}")
            if node.prompt is not None:
                snippet = (
                    node.prompt[:_PROMPT_SNIPPET_LEN] + "..." if len(node.prompt) > _PROMPT_SNIPPET_LEN else node.prompt
                )
                parts.append(f"prompt={snippet!r}")
            lines.append(" ".join(parts))

        lines.append("")
        lines.append("Edges:")
        for edge in pipeline.edges:
            parts = [f"  {edge.source_id} -> {edge.target_id}"]
            if edge.condition is not None:
                parts.append(f"[condition: {edge.condition}]")
            if edge.label is not None:
                parts.append(f"[label: {edge.label}]")
            lines.append(" ".join(parts))

        return "\n".join(lines)
