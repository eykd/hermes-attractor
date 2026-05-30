"""Pydot-based DOT serializer adapter for the DotSerializer port.

This adapter owns the pydot dependency. It must NEVER be imported from the
domain or use_cases layers — only from adapters, plugin, or tests.

See: specs/001-attractor-kanban/contracts/ports.md §DotSerializer
"""

from __future__ import annotations

import base64
import json

import pydot

from hermes_attractor.domain.constants import DOT_MAX_EDGES, DOT_MAX_INPUT_BYTES, DOT_MAX_NODES
from hermes_attractor.domain.exceptions import PipelineValidationError, ValidationIssue
from hermes_attractor.domain.pipeline import Edge, Node, NodeShape, Pipeline, StyleRule, Stylesheet

#: Mapping from Graphviz DOT shape attribute to NodeShape enum value.
_DOT_SHAPE_TO_NODE_SHAPE: dict[str, NodeShape] = {shape.value: shape for shape in NodeShape}


_DOT_MIN_QUOTED_LEN = 2


def _strip_quotes(value: str) -> str:
    r"""Strip surrounding double-quotes and unescape DOT escape sequences.

    pydot returns attribute values wrapped in double-quotes with embedded
    double-quotes escaped as ``\"`` (e.g. ``'"Say \"hello\""'``).
    This removes the outer quotes and unescapes ``\"`` to ``"`` so the
    original value is recovered.

    Args:
        value: The raw attribute value string from pydot.

    Returns:
        The unquoted, unescaped string value.
    """
    inner = (
        value[1:-1] if value.startswith('"') and value.endswith('"') and len(value) >= _DOT_MIN_QUOTED_LEN else value
    )
    return inner.replace('\\"', '"')


class PydotSerializer:
    """DOT serializer adapter using pydot for parsing and emission.

    Implements the DotSerializer port. This class is the only place in the
    codebase that imports pydot.
    """

    def parse(self, dot: str) -> Pipeline:
        """Parse a DOT string into a Pipeline aggregate.

        Enforces resource limits before constructing the Pipeline:
        - Input size capped at DOT_MAX_INPUT_BYTES (1 MiB).
        - Parsed graph must have <= DOT_MAX_NODES (256) nodes.
        - Parsed graph must have <= DOT_MAX_EDGES (1024) edges.

        Args:
            dot: A Graphviz DOT string.

        Returns:
            A Pipeline populated from the DOT definition.

        Raises:
            PipelineValidationError: If input exceeds resource limits or is malformed.
        """
        raw_bytes = dot.encode("utf-8")
        if len(raw_bytes) > DOT_MAX_INPUT_BYTES:
            msg = f"DOT input size {len(raw_bytes)} bytes exceeds limit of {DOT_MAX_INPUT_BYTES}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="pipeline", reason=msg)],
                message="DOT input too large",
            )

        graphs = pydot.graph_from_dot_data(dot)
        if not graphs:
            msg = "DOT input produced no graphs"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="pipeline", reason=msg)],
                message="DOT parse error",
            )

        graph = graphs[0]
        raw_name = graph.get_name()
        spec_id = _strip_quotes(raw_name) if raw_name else "unnamed"

        pydot_nodes = graph.get_nodes()
        pydot_edges = graph.get_edges()

        if len(pydot_nodes) > DOT_MAX_NODES:
            msg = f"Graph has {len(pydot_nodes)} nodes, exceeding limit of {DOT_MAX_NODES}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="pipeline", reason=msg)],
                message="Graph too large (nodes)",
            )

        if len(pydot_edges) > DOT_MAX_EDGES:
            msg = f"Graph has {len(pydot_edges)} edges, exceeding limit of {DOT_MAX_EDGES}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="pipeline", reason=msg)],
                message="Graph too large (edges)",
            )

        nodes = [self._parse_node(n) for n in pydot_nodes]
        edges = [self._parse_edge(e) for e in pydot_edges]
        stylesheet = self._parse_stylesheet(graph)

        return Pipeline(
            spec_id=spec_id,
            nodes=nodes,
            edges=edges,
            stylesheet=stylesheet,
        )

    def _parse_stylesheet(self, graph: pydot.Dot) -> Stylesheet:
        """Decode stylesheet rules from the graph's ``attractor_stylesheet`` attribute.

        The attribute is a base64-encoded JSON list of ``{selector, profile}`` dicts.
        If absent or malformed, an empty Stylesheet is returned.

        Args:
            graph: The pydot graph to read the attribute from.

        Returns:
            A Stylesheet decoded from the graph attribute, or an empty one.
        """
        raw = graph.get_attributes().get("attractor_stylesheet")
        if raw is None:
            return Stylesheet(rules=[])
        try:
            b64 = _strip_quotes(str(raw))
            decoded = json.loads(base64.b64decode(b64.encode()).decode())
            rules = [StyleRule(selector=str(r["selector"]), profile=str(r["profile"])) for r in decoded]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):  # pragma: no cover  # defensive
            return Stylesheet(rules=[])
        return Stylesheet(rules=rules)

    def _parse_node(self, pydot_node: pydot.Node) -> Node:
        """Convert a pydot node to a domain Node.

        Args:
            pydot_node: The pydot Node to convert.

        Returns:
            A domain Node with attributes mapped from DOT attributes.
        """
        node_id = _strip_quotes(pydot_node.get_name())
        attrs = pydot_node.get_attributes()
        shape_str = _strip_quotes(attrs.get("shape", ""))
        shape = _DOT_SHAPE_TO_NODE_SHAPE.get(shape_str, NodeShape.CODERGEN)
        profile_raw = attrs.get("profile")
        profile = _strip_quotes(profile_raw) if profile_raw else None
        prompt_raw = attrs.get("prompt")
        prompt = _strip_quotes(prompt_raw) if prompt_raw else None
        node_class_raw = attrs.get("class")
        node_class = _strip_quotes(node_class_raw) if node_class_raw else None
        retry_limit_raw = attrs.get("retry_limit", "0")
        try:
            retry_limit = int(_strip_quotes(str(retry_limit_raw)))
        except (ValueError, TypeError):  # pragma: no cover  # defensive: pydot returns strings
            retry_limit = 0
        return Node(
            node_id=node_id,
            shape=shape,
            prompt=prompt,
            profile=profile,
            retry_limit=retry_limit,
            node_class=node_class,
        )

    def _parse_edge(self, pydot_edge: pydot.Edge) -> Edge:
        """Convert a pydot edge to a domain Edge.

        Args:
            pydot_edge: The pydot Edge to convert.

        Returns:
            A domain Edge with attributes mapped from DOT attributes.
        """
        source_id = _strip_quotes(str(pydot_edge.get_source()))
        target_id = _strip_quotes(str(pydot_edge.get_destination()))
        attrs = pydot_edge.get_attributes()
        condition_raw = attrs.get("condition")
        stripped_condition = _strip_quotes(condition_raw) if condition_raw else None
        condition = stripped_condition if stripped_condition else None
        label_raw = attrs.get("label")
        label = _strip_quotes(label_raw) if label_raw else None
        weight_raw = attrs.get("weight", "0")
        try:
            weight = int(_strip_quotes(str(weight_raw)))
        except (ValueError, TypeError):  # pragma: no cover  # defensive: pydot returns strings
            weight = 0
        return Edge(
            source_id=source_id,
            target_id=target_id,
            condition=condition,
            label=label,
            weight=weight,
        )

    def _emit_stylesheet(self, graph: pydot.Dot, stylesheet: Stylesheet) -> None:
        """Encode stylesheet rules onto the graph as a base64-encoded JSON attribute.

        If the stylesheet is empty, no attribute is written.

        Args:
            graph: The pydot graph to annotate.
            stylesheet: The Stylesheet to encode.
        """
        if not stylesheet.rules:
            return
        rules_json = json.dumps([{"selector": r.selector, "profile": r.profile} for r in stylesheet.rules])
        b64 = base64.b64encode(rules_json.encode()).decode()
        graph.obj_dict["attributes"]["attractor_stylesheet"] = f'"{b64}"'

    def _emit_node(self, node: Node) -> pydot.Node:
        """Build a pydot Node from a domain Node.

        Args:
            node: The domain Node to convert.

        Returns:
            A pydot Node with DOT attributes set.
        """
        attrs: dict[str, str] = {"shape": node.shape.dot_shape}
        if node.profile is not None:
            attrs["profile"] = node.profile
        if node.prompt is not None:
            attrs["prompt"] = node.prompt
        if node.node_class is not None:
            attrs["class"] = node.node_class
        if node.retry_limit != 0:
            attrs["retry_limit"] = str(node.retry_limit)
        return pydot.Node(node.node_id, **attrs)  # pyright: ignore[reportArgumentType]

    def _emit_edge(self, edge: Edge) -> pydot.Edge:
        """Build a pydot Edge from a domain Edge.

        Args:
            edge: The domain Edge to convert.

        Returns:
            A pydot Edge with DOT attributes set.
        """
        edge_attrs: dict[str, str] = {}
        if edge.condition is not None:
            edge_attrs["condition"] = edge.condition
        if edge.label is not None:
            edge_attrs["label"] = edge.label
        if edge.weight != 0:
            edge_attrs["weight"] = str(edge.weight)
        return pydot.Edge(edge.source_id, edge.target_id, **edge_attrs)  # pyright: ignore[reportArgumentType]

    def emit(self, pipeline: Pipeline) -> str:
        """Serialize a Pipeline aggregate to a DOT string.

        Args:
            pipeline: The pipeline to serialize.

        Returns:
            A valid Graphviz DOT string.
        """
        graph = pydot.Dot(graph_name=pipeline.spec_id, graph_type="digraph")
        self._emit_stylesheet(graph, pipeline.stylesheet)
        for node in pipeline.nodes:
            graph.add_node(self._emit_node(node))
        for edge in pipeline.edges:
            graph.add_edge(self._emit_edge(edge))
        return graph.to_string()
