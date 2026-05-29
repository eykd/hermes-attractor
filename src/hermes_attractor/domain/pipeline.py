"""Pipeline domain model: NodeShape, GoalGatePolicy, Node, Edge, Stylesheet, Pipeline.

This module contains the pure domain aggregate for an Attractor pipeline. It has
ZERO external dependencies — no pydot, no sqlite, no I/O. All validation is
non-raising (Pipeline.validate returns issues rather than raising).

See: specs/001-attractor-kanban/data-model.md §Domain entities
"""

from __future__ import annotations

import copy
import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from hermes_attractor.domain.exceptions import ValidationIssue

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class NodeShape(enum.Enum):
    """Selects a node's handler and maps to a Graphviz DOT shape attribute (FR-006).

    Attributes:
        START: Unique entry point for the pipeline.
        EXIT: Unique terminus for the pipeline.
        CODERGEN: Agent work dispatched via a Kanban card.
        CONDITIONAL: Guard-based routing node.
        TOOL: Deterministic, non-agent computation stage.
        FAN_OUT: Spawns concurrent branches.
        FAN_IN: Merges concurrent branch contexts.
        HUMAN: Durable pause for human input/approval.
    """

    START = "Mdiamond"
    EXIT = "Msquare"
    CODERGEN = "box"
    CONDITIONAL = "diamond"
    TOOL = "parallelogram"
    FAN_OUT = "component"
    FAN_IN = "tripleoctagon"
    HUMAN = "hexagon"

    @property
    def dot_shape(self) -> str:
        """Return the Graphviz DOT shape string for this NodeShape."""
        return self.value


@dataclass(frozen=True)
class GoalGatePolicy:
    """Encodes a goal gate's retry routing for acyclic loops (FR-009, research D4).

    Attributes:
        retry_target: The node_id traversal routes to when the goal is unsatisfied.
        max_attempts: Maximum attempts before the run is blocked for human review; >= 1.
    """

    retry_target: str
    max_attempts: int

    def __post_init__(self) -> None:
        """Validate that max_attempts is >= 1."""
        if self.max_attempts < 1:
            msg = f"GoalGatePolicy.max_attempts must be >= 1, got {self.max_attempts}"
            raise ValueError(msg)


@dataclass(frozen=True)
class StyleRule:
    """A single stylesheet rule mapping a selector to a profile (FR-020).

    Selectors:
        ``*``              — universal (lowest specificity)
        ``SHAPE_NAME``     — NodeShape name (e.g. ``CODERGEN``)
        ``.classname``     — node_class (leading ``.``)
        ``#node_id``       — exact node_id (highest specificity)

    Attributes:
        selector: The CSS-like selector string.
        profile: The Hermes profile name to assign when the selector matches.
    """

    selector: str
    profile: str


@dataclass(frozen=True)
class Stylesheet:
    """A sequence of StyleRules with CSS-like specificity resolution (FR-020).

    Specificity order (highest first): ``id > class > shape > universal``.
    When two rules have the same specificity, the last rule wins.

    Attributes:
        rules: Ordered sequence of StyleRules.
    """

    rules: tuple[StyleRule, ...]

    def __init__(self, rules: Sequence[StyleRule]) -> None:
        """Initialise with an ordered sequence of StyleRules.

        Args:
            rules: StyleRule instances in declaration order.
        """
        super().__init__()
        object.__setattr__(self, "rules", tuple(rules))

    def resolve(self, node: Node) -> str | None:
        """Return the highest-specificity matching profile for the given node.

        Specificity: id > class > shape > universal.
        Ties broken by last-rule-wins within the same specificity level.

        Args:
            node: The Node to resolve a profile for.

        Returns:
            The matching profile string, or ``None`` if no rule matches.
        """
        # Specificity levels: 3=id, 2=class, 1=shape, 0=universal
        best_specificity = -1
        best_profile: str | None = None

        for rule in self.rules:
            specificity = self._specificity(rule.selector, node)
            if specificity >= 0 and specificity >= best_specificity:
                best_specificity = specificity
                best_profile = rule.profile

        return best_profile

    @staticmethod
    def _specificity(selector: str, node: Node) -> int:
        """Return the specificity level of a selector for a given node.

        Returns -1 if the selector does not match the node.

        Args:
            selector: The selector string.
            node: The Node to test against.

        Returns:
            Specificity integer (3=id, 2=class, 1=shape, 0=universal), or -1 for no match.
        """
        if selector == "*":
            return 0
        if selector.startswith("#"):
            return 3 if node.node_id == selector[1:] else -1
        if selector.startswith("."):
            return 2 if node.node_class == selector[1:] else -1
        # Shape selector: compare against NodeShape member names
        try:
            shape = NodeShape[selector]
        except KeyError:
            return -1
        else:
            return 1 if node.shape is shape else -1


@dataclass(frozen=True)
class Node:
    """A single stage in an Attractor pipeline (FR-004, FR-006).

    Identity is ``node_id`` (must be the DOT node identifier).

    Attributes:
        node_id: Unique, non-empty identifier within the pipeline.
        shape: The NodeShape that determines dispatch behaviour.
        prompt: Body template for CODERGEN/HUMAN nodes; supports ``$var`` expansion.
        profile: Per-node profile override; if absent the Stylesheet is consulted.
        retry_limit: Maximum card retries before terminal failure (>= 0).
        goal_gate: GoalGatePolicy if this node is a goal gate; None otherwise.
        node_class: CSS-like class for Stylesheet resolution.
    """

    node_id: str
    shape: NodeShape
    prompt: str | None = None
    profile: str | None = None
    retry_limit: int = 0
    goal_gate: GoalGatePolicy | None = None
    node_class: str | None = None

    def __post_init__(self) -> None:
        """Validate node_id is non-empty and retry_limit is >= 0."""
        if not self.node_id:
            msg = "Node.node_id must be non-empty"
            raise ValueError(msg)
        if self.retry_limit < 0:
            msg = f"Node.retry_limit must be >= 0, got {self.retry_limit}"
            raise ValueError(msg)


@dataclass(frozen=True)
class Edge:
    """A directed transition between two nodes (FR-004, FR-007, FR-011).

    Identity is ``(source_id, target_id, label)``.

    Attributes:
        source_id: The node_id this edge originates from.
        target_id: The node_id this edge leads to.
        condition: Guard expression evaluated against the Context (FR-011).
        label: Preferred routing label matching the Outcome's routing hint.
        weight: Tiebreak priority; default 0 (higher = preferred).
    """

    source_id: str
    target_id: str
    condition: str | None = None
    label: str | None = None
    weight: int = 0


def _find_reachable(start_id: str, adjacency: Mapping[str, list[str]]) -> frozenset[str]:
    """Return the set of node_ids reachable from start_id via BFS.

    Args:
        start_id: The node_id to start BFS from.
        adjacency: Mapping from node_id to list of target node_ids.

    Returns:
        Frozenset of reachable node_ids (including start_id).
    """
    visited: set[str] = set()
    queue = [start_id]
    while queue:
        current = queue.pop()
        if current in visited:  # pragma: no cover  # defensive guard; not reachable with filter
            continue
        visited.add(current)
        queue.extend(n for n in adjacency.get(current, []) if n not in visited)
    return frozenset(visited)


@dataclass(frozen=True)
class Pipeline:
    """The Attractor pipeline aggregate root (FR-004, FR-007, FR-019).

    A directed graph of Nodes and Edges. The canonical stored form is DOT.
    Validation is non-raising: ``validate()`` returns a list of issues.

    Attributes:
        spec_id: Stable identity (derived from the ``.dot`` file/graph name).
        nodes: Ordered sequence of Nodes.
        edges: Sequence of Edges.
        stylesheet: Stylesheet for profile resolution fallback.
    """

    spec_id: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    stylesheet: Stylesheet

    def __init__(
        self,
        *,
        spec_id: str,
        nodes: Sequence[Node],
        edges: Sequence[Edge],
        stylesheet: Stylesheet,
    ) -> None:
        """Initialise the Pipeline aggregate.

        Args:
            spec_id: Stable identifier for this pipeline definition.
            nodes: All nodes in the pipeline.
            edges: All directed edges in the pipeline.
            stylesheet: Stylesheet for profile resolution.
        """
        super().__init__()
        object.__setattr__(self, "spec_id", spec_id)
        object.__setattr__(self, "nodes", tuple(nodes))
        object.__setattr__(self, "edges", tuple(edges))
        object.__setattr__(self, "stylesheet", stylesheet)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _adjacency(self) -> dict[str, list[str]]:
        """Return a mapping from node_id to list of reachable target node_ids."""
        adj: dict[str, list[str]] = {node.node_id: [] for node in self.nodes}
        for edge in self.edges:
            if edge.source_id in adj:
                adj[edge.source_id].append(edge.target_id)
        return adj

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self) -> list[ValidationIssue]:
        """Validate the pipeline and return a list of structured issues (non-raising).

        Checks (FR-004, SC-007):
          - Exactly one START and one EXIT node.
          - No dangling edges (all endpoints reference existing nodes).
          - Full reachability from the START node.
          - All goal-gate retry_targets exist and are reachable.
          - All resolved profiles are non-empty.

        Returns:
            A list of ValidationIssue; empty list means the pipeline is valid.
        """
        node_ids = frozenset(n.node_id for n in self.nodes)
        start_nodes = [n for n in self.nodes if n.shape is NodeShape.START]
        issues: list[ValidationIssue] = []
        issues.extend(self._validate_structure(start_nodes))
        issues.extend(self._validate_edges(node_ids))
        reachable = self._validate_reachability(start_nodes, issues)
        issues.extend(self._validate_goal_gates(node_ids, reachable))
        issues.extend(self._validate_profiles())
        return issues

    def _validate_structure(self, start_nodes: list[Node]) -> list[ValidationIssue]:
        """Check that there is exactly one START and one EXIT node.

        Args:
            start_nodes: Pre-filtered list of START nodes.

        Returns:
            List of ValidationIssue for structural violations.
        """
        issues: list[ValidationIssue] = []
        exit_nodes = [n for n in self.nodes if n.shape is NodeShape.EXIT]
        if len(start_nodes) != 1:
            issues.append(
                ValidationIssue(
                    element_id="pipeline",
                    reason=f"Expected exactly one START node, found {len(start_nodes)}",
                )
            )
        if len(exit_nodes) != 1:
            issues.append(
                ValidationIssue(
                    element_id="pipeline",
                    reason=f"Expected exactly one EXIT node, found {len(exit_nodes)}",
                )
            )
        return issues

    def _validate_edges(self, node_ids: frozenset[str]) -> list[ValidationIssue]:
        """Check that all edge endpoints reference existing nodes.

        Args:
            node_ids: Set of all node_ids in the pipeline.

        Returns:
            List of ValidationIssue for dangling edges.
        """
        issues: list[ValidationIssue] = []
        for edge in self.edges:
            if edge.source_id not in node_ids:
                issues.append(
                    ValidationIssue(
                        element_id=edge.source_id,
                        reason=f"Edge source '{edge.source_id}' references a nonexistent node",
                    )
                )
            if edge.target_id not in node_ids:
                issues.append(
                    ValidationIssue(
                        element_id=edge.target_id,
                        reason=f"Edge target '{edge.target_id}' references a nonexistent node",
                    )
                )
        return issues

    def _validate_reachability(self, start_nodes: list[Node], issues: list[ValidationIssue]) -> frozenset[str]:
        """Check reachability from START; append issues and return the reachable set.

        Args:
            start_nodes: Pre-filtered list of START nodes.
            issues: Mutable list to append unreachability issues to.

        Returns:
            Frozenset of reachable node_ids; empty if there is not exactly one START.
        """
        if len(start_nodes) != 1:
            return frozenset()
        reachable = _find_reachable(start_nodes[0].node_id, self._adjacency())
        issues.extend(
            ValidationIssue(
                element_id=node.node_id,
                reason=f"Node '{node.node_id}' is unreachable from START",
            )
            for node in self.nodes
            if node.node_id not in reachable
        )
        return reachable

    def _validate_goal_gates(self, node_ids: frozenset[str], reachable: frozenset[str]) -> list[ValidationIssue]:
        """Check that goal-gate retry_targets exist and are reachable.

        Args:
            node_ids: Set of all node_ids in the pipeline.
            reachable: Frozenset of reachable node_ids (empty if START is missing).

        Returns:
            List of ValidationIssue for invalid goal-gate retry_targets.
        """
        issues: list[ValidationIssue] = []
        for node in self.nodes:
            if node.goal_gate is None:
                continue
            target = node.goal_gate.retry_target
            if target not in node_ids:
                issues.append(
                    ValidationIssue(
                        element_id=node.node_id,
                        reason=(
                            f"Goal gate retry_target '{target}' on node '{node.node_id}' references a nonexistent node"
                        ),
                    )
                )
            elif reachable and target not in reachable:
                issues.append(
                    ValidationIssue(
                        element_id=node.node_id,
                        reason=(
                            f"Goal gate retry_target '{target}' on node '{node.node_id}' is unreachable from START"
                        ),
                    )
                )
        return issues

    def _validate_profiles(self) -> list[ValidationIssue]:
        """Check that all worker nodes have a resolved profile.

        Returns:
            List of ValidationIssue for nodes with no resolved profile.
        """
        worker_shapes = {
            NodeShape.CODERGEN,
            NodeShape.CONDITIONAL,
            NodeShape.TOOL,
            NodeShape.FAN_OUT,
            NodeShape.FAN_IN,
            NodeShape.HUMAN,
        }
        return [
            ValidationIssue(
                element_id=node.node_id,
                reason=(
                    f"Node '{node.node_id}' has no resolved profile"
                    " (no per-node override and no matching stylesheet rule)"
                ),
            )
            for node in self.nodes
            if node.shape in worker_shapes and not self.resolve_profile(node)
        ]

    def resolve_profile(self, node: Node) -> str | None:
        """Return the resolved profile for a node (FR-019 overrides FR-020).

        Priority: per-node ``profile`` > stylesheet resolution.

        Args:
            node: The node to resolve a profile for.

        Returns:
            The resolved profile string, or ``None`` if no profile is available.
        """
        if node.profile is not None:
            return node.profile
        return self.stylesheet.resolve(node)


@dataclass(frozen=True)
class Context:
    """Shared key/value state threaded through a Run (FR-008).

    Immutable: mutation operations return new instances.

    Attributes:
        data: JSON-serializable mapping of context keys to values.
    """

    data: Mapping[str, object]

    def __init__(self, data: Mapping[str, object]) -> None:
        """Initialise with a key/value mapping.

        Args:
            data: JSON-serializable mapping of context keys to values.
        """
        super().__init__()
        object.__setattr__(self, "data", dict(data))

    def apply(self, updates: Mapping[str, object]) -> Context:
        """Return a new Context with the given updates applied.

        Args:
            updates: Key/value pairs to merge into the current data.

        Returns:
            A new Context with the merged data.
        """
        merged = {**self.data, **updates}
        return Context(data=merged)

    def clone(self) -> Context:
        """Return a deep copy of this Context for fan-out branches.

        Returns:
            A new Context with a deep-copied data mapping.
        """
        return Context(data=copy.deepcopy(dict(self.data)))

    def merge(self, branches: Sequence[Context]) -> Context:
        """Return a new Context that merges branch contexts (deterministic fan-in).

        Rules (R-MERGE):
          - Disjoint keys are unioned.
          - Conflicting keys: last-writer-by-branch-order wins; conflicts recorded
            under the reserved ``_merge_conflicts`` key.
          - Same-key lists are concatenated in branch order.

        Args:
            branches: Ordered sequence of branch Contexts to merge.

        Returns:
            A new Context with the merged data.
        """
        merged: dict[str, object] = dict(self.data)
        conflicts: dict[str, list[object]] = {}

        for branch in branches:
            for key, value in branch.data.items():
                if key.startswith("_"):
                    continue  # skip reserved keys
                if key in merged:
                    existing = merged[key]
                    if isinstance(existing, list) and isinstance(value, list):
                        existing_list: list[object] = cast("list[object]", existing)
                        value_list: list[object] = cast("list[object]", value)
                        merged[key] = existing_list + value_list
                    else:
                        if key not in conflicts:
                            conflicts[key] = [existing]
                        conflicts[key].append(value)
                        merged[key] = value
                else:
                    merged[key] = value

        if conflicts:
            merged["_merge_conflicts"] = conflicts

        return Context(data=merged)
