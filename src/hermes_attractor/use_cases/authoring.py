"""Authoring use cases for pipeline creation and modification (FR-001, FR-002, FR-004, FR-005).

Each function follows the load -> modify -> (optionally validate) -> save pattern.
Use cases are pure application logic; they delegate I/O to ports.

See: specs/001-attractor-kanban/contracts/tools.md §Authoring tools
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes_attractor.domain.pipeline import Edge, Node, NodeShape, Pipeline, StyleRule, Stylesheet

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hermes_attractor.ports.dot import DotSerializer
    from hermes_attractor.ports.pipeline_store import PipelineStore
    from hermes_attractor.ports.renderer import Renderer


def create_graph(
    *,
    spec_id: str,
    store: PipelineStore,
    serializer: DotSerializer,
) -> None:
    """Create a new empty pipeline and persist it via the store.

    Args:
        spec_id: The identifier for the new pipeline.
        store: PipelineStore adapter for persistence.
        serializer: DotSerializer adapter for DOT emission.
    """
    pipeline = Pipeline(
        spec_id=spec_id,
        nodes=[],
        edges=[],
        stylesheet=Stylesheet(rules=[]),
    )
    dot = serializer.emit(pipeline)
    store.save(spec_id, dot)


def add_node(  # noqa: PLR0913  # domain API requires all node-creation params as kwargs
    *,
    spec_id: str,
    node_id: str,
    shape: NodeShape,
    prompt: str | None = None,
    profile: str | None = None,
    retry_limit: int = 0,
    node_class: str | None = None,
    store: PipelineStore,
    serializer: DotSerializer,
) -> Pipeline:
    """Load the pipeline, add a node, and save the updated definition.

    Args:
        spec_id: The pipeline identifier.
        node_id: The new node's identifier.
        shape: The NodeShape for the new node.
        prompt: Optional prompt template.
        profile: Optional per-node profile override.
        retry_limit: Maximum card retries (>= 0).
        node_class: Optional stylesheet class for the node.
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        The updated Pipeline aggregate.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    new_node = Node(
        node_id=node_id,
        shape=shape,
        prompt=prompt,
        profile=profile,
        retry_limit=retry_limit,
        node_class=node_class,
    )
    updated = Pipeline(
        spec_id=pipeline.spec_id,
        nodes=[*pipeline.nodes, new_node],
        edges=list(pipeline.edges),
        stylesheet=pipeline.stylesheet,
    )
    store.save(spec_id, serializer.emit(updated))
    return updated


def remove_node(
    *,
    spec_id: str,
    node_id: str,
    store: PipelineStore,
    serializer: DotSerializer,
) -> Pipeline:
    """Load the pipeline, remove a node (and its connected edges), and save.

    Args:
        spec_id: The pipeline identifier.
        node_id: The node_id to remove.
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        The updated Pipeline aggregate.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    updated = Pipeline(
        spec_id=pipeline.spec_id,
        nodes=[n for n in pipeline.nodes if n.node_id != node_id],
        edges=[e for e in pipeline.edges if node_id not in (e.source_id, e.target_id)],
        stylesheet=pipeline.stylesheet,
    )
    store.save(spec_id, serializer.emit(updated))
    return updated


def add_edge(  # noqa: PLR0913  # domain API requires all edge-creation params as kwargs
    *,
    spec_id: str,
    source_id: str,
    target_id: str,
    condition: str | None = None,
    label: str | None = None,
    weight: int = 0,
    store: PipelineStore,
    serializer: DotSerializer,
) -> Pipeline:
    """Load the pipeline, add an edge, and save the updated definition.

    Args:
        spec_id: The pipeline identifier.
        source_id: The source node_id.
        target_id: The target node_id.
        condition: Optional guard condition string.
        label: Optional routing label.
        weight: Edge weight (default 0).
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        The updated Pipeline aggregate.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    new_edge = Edge(
        source_id=source_id,
        target_id=target_id,
        condition=condition,
        label=label,
        weight=weight,
    )
    updated = Pipeline(
        spec_id=pipeline.spec_id,
        nodes=list(pipeline.nodes),
        edges=[*pipeline.edges, new_edge],
        stylesheet=pipeline.stylesheet,
    )
    store.save(spec_id, serializer.emit(updated))
    return updated


def remove_edge(  # noqa: PLR0913  # domain API requires all removal params as kwargs
    *,
    spec_id: str,
    source_id: str,
    target_id: str,
    label: str | None = None,
    store: PipelineStore,
    serializer: DotSerializer,
) -> Pipeline:
    """Load the pipeline, remove a matching edge, and save.

    Args:
        spec_id: The pipeline identifier.
        source_id: The source node_id of the edge to remove.
        target_id: The target node_id of the edge to remove.
        label: Optional label to narrow the match (if multiple edges between the same pair).
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        The updated Pipeline aggregate.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    updated = Pipeline(
        spec_id=pipeline.spec_id,
        nodes=list(pipeline.nodes),
        edges=[
            e
            for e in pipeline.edges
            if not (e.source_id == source_id and e.target_id == target_id and (label is None or e.label == label))
        ],
        stylesheet=pipeline.stylesheet,
    )
    store.save(spec_id, serializer.emit(updated))
    return updated


def set_stylesheet(
    *,
    spec_id: str,
    rules: Sequence[StyleRule],
    store: PipelineStore,
    serializer: DotSerializer,
) -> Pipeline:
    """Load the pipeline, replace the stylesheet, and save.

    Args:
        spec_id: The pipeline identifier.
        rules: The new StyleRule sequence for the Stylesheet.
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        The updated Pipeline aggregate.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    updated = Pipeline(
        spec_id=pipeline.spec_id,
        nodes=list(pipeline.nodes),
        edges=list(pipeline.edges),
        stylesheet=Stylesheet(rules=list(rules)),
    )
    store.save(spec_id, serializer.emit(updated))
    return updated


def validate_pipeline(
    *,
    spec_id: str,
    store: PipelineStore,
    serializer: DotSerializer,
) -> dict[str, object]:
    """Load and validate the pipeline; return a structured result.

    Args:
        spec_id: The pipeline identifier.
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.

    Returns:
        A dict with ``valid`` (bool) and ``issues`` (list of {element_id, reason} dicts).
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    issues = pipeline.validate()
    return {
        "valid": len(issues) == 0,
        "issues": [{"element_id": i.element_id, "reason": i.reason} for i in issues],
    }


def get_summary(
    *,
    spec_id: str,
    store: PipelineStore,
    serializer: DotSerializer,
    renderer: Renderer,
) -> dict[str, object]:
    """Load the pipeline and return a human-readable summary plus the raw DOT.

    Args:
        spec_id: The pipeline identifier.
        store: PipelineStore adapter.
        serializer: DotSerializer adapter.
        renderer: Renderer adapter.

    Returns:
        A dict with ``summary`` (str) and ``dot`` (str) keys.
    """
    dot = store.load(spec_id)
    pipeline = serializer.parse(dot)
    summary = renderer.summarize(pipeline)
    return {"summary": summary, "dot": dot}
