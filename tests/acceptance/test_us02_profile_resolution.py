"""Acceptance tests for US2: Launch and execute a linear pipeline with per-node profiles.

Acceptance spec: specs/acceptance-specs/US02-profile-resolution.txt

Scenarios covered:

  1. GIVEN a pipeline whose nodes use a stylesheet default profile and one node has a
     per-node profile override WHEN the pipeline runs THEN each work node creates a kanban
     card assigned to the resolved profile AND the per-node override takes precedence over
     the stylesheet default.
"""

from __future__ import annotations

import datetime
import json
from typing import cast
from unittest.mock import MagicMock

import pytest

from hermes_attractor.domain.card import CardKind, CardResult
from hermes_attractor.domain.pipeline import (
    Edge,
    Node,
    NodeShape,
    Pipeline,
    StyleRule,
    Stylesheet,
)
from hermes_attractor.domain.run import RunStatus
from hermes_attractor.plugin.tools import (
    handle_attractor_run,
    handle_attractor_status,
)
from hermes_attractor.use_cases.run_execution import advance_on_completion

pytestmark = pytest.mark.integration

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _ok(response: str) -> dict[str, object]:
    """Assert response is ok:true and return the result field."""
    data: dict[str, object] = json.loads(response)
    assert data.get("ok") is True, f"Expected ok:true, got: {data}"
    result = data.get("result", {})
    assert isinstance(result, dict)
    return result  # pyright: ignore[reportUnknownVariableType]


def _make_profile_test_pipeline() -> Pipeline:
    """Build a pipeline: start -> default_node -> override_node -> exit.

    ``default_node`` uses the stylesheet default profile ("default-profile").
    ``override_node`` uses the per-node override profile ("override-profile").
    """
    start = Node(node_id="start", shape=NodeShape.START)
    default_node = Node(
        node_id="default_node",
        shape=NodeShape.CODERGEN,
        prompt="Do the default work.",
        # profile is None — should fall back to stylesheet default
    )
    override_node = Node(
        node_id="override_node",
        shape=NodeShape.CODERGEN,
        prompt="Do the specialized work.",
        profile="override-profile",  # per-node override
    )
    exit_ = Node(node_id="exit", shape=NodeShape.EXIT)
    edges = [
        Edge(source_id="start", target_id="default_node"),
        Edge(source_id="default_node", target_id="override_node"),
        Edge(source_id="override_node", target_id="exit"),
    ]
    stylesheet = Stylesheet(rules=[StyleRule(selector="*", profile="default-profile")])
    return Pipeline(
        spec_id="profile_test",
        nodes=[start, default_node, override_node, exit_],
        edges=edges,
        stylesheet=stylesheet,
    )


def test_per_node_profile_override_takes_precedence() -> None:  # noqa: PLR0915
    """Per-node profile override takes precedence over stylesheet default.

    GIVEN a pipeline whose nodes use a stylesheet default profile and one node has a
    per-node profile override
    WHEN the pipeline runs
    THEN the first card is assigned to the resolved profile (stylesheet default)
    THEN the node with the per-node override is assigned that override profile,
         not the stylesheet default.
    """
    pipeline = _make_profile_test_pipeline()

    # Fake kanban board — records all created cards, returns unique task ids.
    created_cards: list[object] = []
    task_counter: list[int] = [0]

    def _create_card(card: object) -> str:
        """Record the card and return a unique task id."""
        created_cards.append(card)
        task_counter[0] += 1
        return f"task-{task_counter[0]:03d}"

    kanban = MagicMock()
    kanban.create_card.side_effect = _create_card

    # Fake run state store.
    runs: dict[str, object] = {}
    nodes: list[object] = []

    def _create_run(run: object) -> None:
        """Store the run."""
        runs[run.run_id] = run  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

    def _get_run(run_id: str) -> object:
        """Return the stored run."""
        return runs.get(run_id)

    def _upsert_node(node: object) -> None:
        """Store the node."""
        nodes.append(node)

    def _nodes_for_run(run_id: str) -> list[object]:
        """Return all nodes for the run."""
        return [n for n in nodes if n.run_id == run_id]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

    run_state = MagicMock()
    run_state.create_run.side_effect = _create_run
    run_state.get_run.side_effect = _get_run
    run_state.upsert_node.side_effect = _upsert_node
    run_state.nodes_for_run.side_effect = _nodes_for_run

    serializer = MagicMock()
    serializer.parse.return_value = pipeline

    store = MagicMock()
    store.load.return_value = "digraph profile_test {}"

    clock = MagicMock()
    clock.now.return_value = _NOW

    profile_registry = MagicMock()
    profile_registry.exists.return_value = True

    # Launch the run.
    run_result = _ok(
        handle_attractor_run(
            {"spec_id": "profile_test", "context": {}},
            kanban=kanban,
            run_state=run_state,
            serializer=serializer,
            store=store,
            clock=clock,
            profile_registry=profile_registry,
        )
    )
    run_id = str(run_result["run_id"])

    # Verify run is RUNNING.
    assert run_result["status"] == RunStatus.RUNNING.value

    # The first card should have been created for 'default_node' with the stylesheet default.
    assert len(created_cards) == 1
    first_card = created_cards[0]
    assert first_card.assignee_profile == "default-profile"  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert first_card.kind is CardKind.WORK  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

    # Query status.
    status_result = _ok(handle_attractor_status({"run_id": run_id}, run_state=run_state))
    assert status_result.get("run_id") == run_id
    assert status_result.get("status") == RunStatus.RUNNING.value
    current_nodes = cast("list[str]", status_result.get("current_nodes", []))
    assert "default_node" in current_nodes

    # Verify the per-node override profile is encoded in the Card's idempotency key.
    # The override_node would get assigned "override-profile" (not "default-profile").
    # We verify by simulating the second advance: complete default_node -> creates override_node card.
    # The RunNode for default_node should be in our fake store.
    default_node_record = next(
        (n for n in nodes if n.node_id == "default_node"),  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        None,
    )
    assert default_node_record is not None, "Expected default_node in run state"

    # Simulate completion of default_node.
    card_result = CardResult(
        task_id=default_node_record.task_id,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownArgumentType]
        event_id=1,
        event_kind="completed",
        summary="Default work done.",
        metadata={},
    )

    run_state.get_node_by_task.return_value = default_node_record
    run_state.get_run.side_effect = _get_run

    advance_on_completion(
        card_result=card_result,
        kanban=kanban,
        run_state=run_state,
        pipeline=pipeline,
        clock=clock,
    )

    # Two cards should now exist: default_node's + override_node's.
    assert len(created_cards) == 2
    override_card = created_cards[1]
    # Per-node override takes precedence: override_node should get "override-profile".
    assert override_card.assignee_profile == "override-profile"  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert override_card.assignee_profile != "default-profile"  # pyright: ignore[reportAttributeAccessIssue]
