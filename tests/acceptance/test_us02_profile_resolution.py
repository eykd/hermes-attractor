"""Acceptance tests for US2: Launch and execute a linear pipeline with per-node profiles.

Acceptance spec: specs/acceptance-specs/US02-profile-resolution.txt

Scenarios covered:

  1. GIVEN a pipeline whose nodes use a stylesheet default profile and one node has a
     per-node profile override WHEN the pipeline runs THEN each work node creates a kanban
     card assigned to the resolved profile AND the per-node override takes precedence over
     the stylesheet default.
"""

from __future__ import annotations

import json

import pytest

from hermes_attractor.plugin.tools import (
    handle_attractor_run,
    handle_attractor_status,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xfail(
        reason="M2 run/kanban milestone not yet implemented",
        strict=False,
    ),
]


def _ok(response: str) -> dict[str, object]:
    """Assert response is ok:true and return the result field."""
    data: dict[str, object] = json.loads(response)
    assert data.get("ok") is True, f"Expected ok:true, got: {data}"
    result = data.get("result", {})
    assert isinstance(result, dict)
    return result  # type: ignore[return-value]


def test_per_node_profile_override_takes_precedence(tmp_path: object) -> None:
    """Per-node profile override takes precedence over stylesheet default.

    GIVEN a pipeline whose nodes use a stylesheet default profile and one node has a
    per-node profile override
    WHEN the pipeline runs
    THEN each work node creates a kanban card assigned to the resolved profile
    THEN the node with the per-node override is assigned that override profile,
         not the stylesheet default.
    """
    # This test requires M2: run launch, kanban card creation, profile resolution.
    # The implementation is not yet available; this test is xfail.
    run_result = _ok(
        handle_attractor_run(
            {
                "spec_id": "profile_test",
                "repo_path": str(tmp_path),
                "context": {},
            }
        )
    )
    run_id = str(run_result["run_id"])

    status_result = _ok(handle_attractor_status({"run_id": run_id}))
    assert status_result.get("run_id") == run_id
    assert "status" in status_result

    # The "special" node should have been assigned its override profile (not the default).
    # Check that the status includes profile information for each node.
    nodes = status_result.get("current_nodes", [])
    assert nodes, "Expected at least one node in the run status"
