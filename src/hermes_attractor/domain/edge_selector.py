"""EdgeSelector domain service: deterministic, total edge selection (FR-007).

Priority order (highest first):
  1. Edges whose ``condition`` guard evaluates True against the Context.
  2. Edges whose ``label`` matches the routing ``routing_hint`` from the Outcome.
  3. Edges whose ``target_id`` is in ``suggested_nodes`` (from the Outcome).
  4. Highest ``weight``.
  5. Lexically smallest ``target_id`` (stable tiebreak for replay-safety).

A ``condition`` that evaluates False **disqualifies** the edge entirely.
An edge with no condition (``condition is None``) passes the condition filter.

See: specs/001-attractor-kanban/data-model.md §EdgeSelector, plan.md §M1
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes_attractor.domain.guard import evaluate

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from hermes_attractor.domain.pipeline import Edge


def select(
    edges: Sequence[Edge],
    *,
    context: Mapping[str, object],
    routing_hint: str | None,
    suggested_nodes: Sequence[str],
) -> Edge | None:
    """Select the best edge from the candidates using deterministic priority rules.

    This is a pure, total function — identical inputs always yield the same output
    (load-bearing for replay-safety, FR-024).

    Args:
        edges: Candidate edges to select from.
        context: The current pipeline run context (evaluated against guard conditions).
        routing_hint: Optional label hint from the Outcome (from a ``label``-based route).
        suggested_nodes: Optional list of suggested next node_ids from the Outcome.

    Returns:
        The selected Edge, or ``None`` if no candidates exist.
    """
    if not edges:
        return None

    # Pre-compute condition results once per edge to avoid redundant evaluate() calls.
    # None condition means unconditioned (always passes); True means condition matched.
    condition_results: dict[int, bool] = {
        id(edge): evaluate(edge.condition, context) for edge in edges if edge.condition is not None
    }

    # Filter out edges whose condition evaluates False.
    candidates = [edge for edge in edges if edge.condition is None or condition_results[id(edge)]]
    if not candidates:
        return None

    # Score each candidate: higher is better.
    # Priority vector: (condition_match, label_match, suggested_match, weight, lexical)
    # We negate weight and use target_id directly for lexical (ascending).
    def _score(edge: Edge) -> tuple[int, int, int, int, str]:
        """Compute a sort key for an edge (higher score = better candidate).

        Args:
            edge: The edge to score.

        Returns:
            Tuple where higher values mean more preferred (except target_id, ascending).
        """
        condition_score = 1 if edge.condition is not None and condition_results[id(edge)] else 0
        label_score = 1 if routing_hint is not None and edge.label == routing_hint else 0
        suggested_score = 1 if edge.target_id in suggested_nodes else 0
        return (condition_score, label_score, suggested_score, edge.weight, edge.target_id)

    # Sort by descending priority for everything except target_id (ascending lexical).
    # We use a composite key: negate integer scores and leave target_id as-is.
    def _sort_key(edge: Edge) -> tuple[int, int, int, int, str]:
        """Compute the sort key with negation for descending sort on integer scores.

        Args:
            edge: The edge to sort.

        Returns:
            Sort key tuple (negated integer scores for descending, target_id ascending).
        """
        c, lb, s, w, t = _score(edge)
        return (-c, -lb, -s, -w, t)

    return min(candidates, key=_sort_key)
