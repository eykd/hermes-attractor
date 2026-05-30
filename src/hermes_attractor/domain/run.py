"""Run domain state machine: RunStatus, NodeRunStatus, Run, RunNode, IdempotencyKey.

Pure domain records describing the persisted state of a pipeline execution.
Zero external dependencies — no I/O, no adapters.

See: specs/001-attractor-kanban/data-model.md §Run-state entities
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from hermes_attractor.domain.pipeline import Context, GoalGatePolicy

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _empty_str_obj_dict() -> dict[str, object]:
    """Return a new empty dict[str, object] for use as a dataclass field default_factory."""
    return {}


class RunStatus(enum.Enum):
    """Lifecycle status of a pipeline Run.

    State machine transitions (enforced at the domain layer)::

        PENDING -> RUNNING               (launch)
        RUNNING -> PAUSED_HUMAN          (reached a HUMAN node)
        PAUSED_HUMAN -> RUNNING          (human input received)
        RUNNING -> BLOCKED               (goal-gate exhausted / terminal node failure)
        RUNNING -> SUCCEEDED             (reached EXIT, all goal gates satisfied)
        RUNNING -> FAILED                (terminal failure, no recovery; FR-016)

    Attributes:
        PENDING: Run created but not yet started.
        RUNNING: Run is actively executing.
        PAUSED_HUMAN: Run is waiting for a human response at a HUMAN node.
        BLOCKED: Run is halted pending human review (goal-gate attempts exhausted
            or terminal node failure awaiting intervention).
        SUCCEEDED: Run completed successfully (reached EXIT with all gates satisfied).
        FAILED: Run terminated with no recovery path (FR-016).
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED_HUMAN = "PAUSED_HUMAN"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class NodeRunStatus(enum.Enum):
    """Lifecycle status of a single RunNode within a Run.

    Typical progression::

        PENDING -> DISPATCHED -> RUNNING -> SUCCEEDED
                                         -> PARTIAL    (goal gate not satisfied)
                                         -> FAILED     (unrecoverable error)
                                         -> BLOCKED    (awaiting human review)

    Attributes:
        PENDING: Node not yet started.
        DISPATCHED: Card created on the kanban board; awaiting pickup.
        RUNNING: Node's card is actively being executed.
        SUCCEEDED: Node completed and its goal gate (if any) was satisfied.
        PARTIAL: Node completed but only partially satisfied its goal gate;
            a retry may be scheduled via the GoalGatePolicy.
        FAILED: Node failed unrecoverably (retry limit exhausted).
        BLOCKED: Node is halted pending human review.
    """

    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class IdempotencyKey:
    """Canonical idempotency key for a RunNode dispatch (research D5).

    Format: ``attractor:<run_id>:<node_id>:attempt:<n>``

    Attributes:
        value: The full formatted idempotency key string.
    """

    value: str

    @classmethod
    def for_node(cls, run_id: str, node_id: str, attempt: int) -> IdempotencyKey:
        """Construct an IdempotencyKey for a specific run/node/attempt triple.

        Args:
            run_id: Identifier for the Run. Must not contain colons.
            node_id: Identifier for the Node. Must not contain colons.
            attempt: Attempt number (>= 1).

        Returns:
            An IdempotencyKey with value
            ``attractor:<run_id>:<node_id>:attempt:<attempt>``.

        Raises:
            ValueError: If ``run_id`` or ``node_id`` contain a colon or other
                unsafe characters.
        """
        if not _SAFE_ID_RE.match(run_id):
            msg = f"run_id must match [A-Za-z0-9_-]+, got {run_id!r}"
            raise ValueError(msg)
        if not _SAFE_ID_RE.match(node_id):
            msg = f"node_id must match [A-Za-z0-9_-]+, got {node_id!r}"
            raise ValueError(msg)
        return cls(value=f"attractor:{run_id}:{node_id}:attempt:{attempt}")


@dataclass(frozen=True)
class Run:
    """Durable record of a pipeline execution (maps to ``plugin_runs``).

    Attributes:
        run_id: Stable unique identifier for this run.
        spec_id: The pipeline spec that this run executes.
        status: Current lifecycle status of the run.
        root_task_id: Kanban task id for the root orchestration card, if any.
        last_seen_event_id: Durable replay cursor; the id of the last consumed
            event log entry (FR-024).
        context: Shared key/value state threaded through the run.
        created_at: UTC timestamp when the run was created.
        updated_at: UTC timestamp when the run was last updated.
    """

    run_id: str
    spec_id: str
    status: RunStatus
    context: Context
    created_at: datetime
    updated_at: datetime
    root_task_id: str | None = field(default=None)
    last_seen_event_id: int = field(default=0)


@dataclass(frozen=True)
class RunNode:
    """Durable record of a single node's execution within a run (maps to ``plugin_run_nodes``).

    The composite identity is ``(run_id, node_id, attempt)``, which maps 1:1
    to the idempotency key ``attractor:<run_id>:<node_id>:attempt:<attempt>``.

    Attributes:
        run_id: Identifier for the parent Run.
        node_id: Identifier for the pipeline Node being executed.
        task_id: Kanban task id for the dispatched Card, or None if not yet dispatched.
        status: Current lifecycle status of this node execution.
        attempt: Attempt number; >= 1.
        parent_node_ids: Ordered list of node_ids whose outputs feed into this node.
        goal_gate_policy: Retry policy if this node is a goal gate, else None.
        output_ref: Reference to the node's result artifact, or None.
        context_updates: Context key/value updates contributed by this node (FR-008).
            Stored for FAN_IN merge conflict detection.
    """

    run_id: str
    node_id: str
    status: NodeRunStatus
    attempt: int
    parent_node_ids: Sequence[str]
    task_id: str | None = field(default=None)
    goal_gate_policy: GoalGatePolicy | None = field(default=None)
    output_ref: str | None = field(default=None)
    context_updates: Mapping[str, object] = field(default_factory=_empty_str_obj_dict)

    def __post_init__(self) -> None:
        """Validate invariants after construction.

        Raises:
            ValueError: If ``attempt`` is less than 1.
        """
        if self.attempt < 1:
            msg = f"RunNode.attempt must be >= 1, got {self.attempt}"
            raise ValueError(msg)
