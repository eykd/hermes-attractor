"""Run execution use cases: launch_run and advance_on_completion.

Orchestrates pipeline execution: launching a Run by creating the first
kanban card, and advancing the state machine when a card completes.

Design invariants:
  - ``_expand_prompt`` performs **non-recursive literal substitution** of ``$var``
    placeholders. Undefined variables become ``__UNDEFINED_VAR_<name>__`` in the
    prompt body only — the sentinel string is NEVER written to ``Context.data``.
  - ``advance_on_completion`` is **idempotent** on the same ``card_result``:
    re-running it with the same event_id produces the same net state
    (``upsert_node`` + ``save_run`` are both idempotent write operations).
  - The reconciler (research D2) can reuse ``advance_on_completion`` directly
    for catch-up replay, since the idempotency guarantee holds.

See: specs/001-attractor-kanban/contracts/tools.md §Execution tools
See: specs/001-attractor-kanban/plan.md §M2, §Architecture (use_cases/)
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import TYPE_CHECKING

from hermes_attractor.domain.card import Card, CardKind
from hermes_attractor.domain.constants import MAX_FAN_OUT_WIDTH
from hermes_attractor.domain.edge_selector import select as select_edge
from hermes_attractor.domain.exceptions import PipelineValidationError, ValidationIssue
from hermes_attractor.domain.pipeline import Context, NodeShape, Pipeline
from hermes_attractor.domain.run import IdempotencyKey, NodeRunStatus, Run, RunNode, RunStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hermes_attractor.domain.card import CardResult
    from hermes_attractor.ports.clock import Clock
    from hermes_attractor.ports.dot import DotSerializer
    from hermes_attractor.ports.kanban import KanbanBoard
    from hermes_attractor.ports.pipeline_store import PipelineStore
    from hermes_attractor.ports.run_state import RunStateStore

_log = logging.getLogger(__name__)

#: Sentinel used in prompt expansion when a variable is not found in context.
_UNDEFINED_VAR_SENTINEL = "__UNDEFINED_VAR_{name}__"

#: Gate verdict key in CardResult.metadata (plan.md §Security §Gate-verdict trust).
_GATE_VERDICT_KEY = "gate"
#: Gate verdict value that indicates a pass.
_GATE_PASS_VALUE = "pass"  # noqa: S105  # not a password; this is a domain verdict string


def _expand_prompt(template: str, context: Mapping[str, object]) -> str:
    """Expand ``$var`` placeholders in a prompt template using the context.

    Uses non-recursive, literal substitution (spec FR-022). Undefined variables
    are replaced with ``__UNDEFINED_VAR_<name>__`` (never written to Context.data).

    Args:
        template: The prompt template string with ``$var`` placeholders.
        context: The current run context mapping.

    Returns:
        The expanded prompt string.
    """
    # Convert context values to strings for substitution.
    str_context = {k: str(v) for k, v in context.items()}

    def _replace(match: re.Match[str]) -> str:
        """Replace a matched $var or ${var} placeholder.

        Args:
            match: The regex match object.

        Returns:
            The substituted value string.
        """
        name = match.group(1) or match.group(2)
        return str_context.get(name, _UNDEFINED_VAR_SENTINEL.format(name=name))

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", _replace, template)


def _card_kind_for_node(node_shape: NodeShape) -> CardKind:
    """Map a NodeShape to a CardKind.

    Args:
        node_shape: The NodeShape to map.

    Returns:
        The corresponding CardKind.
    """
    if node_shape is NodeShape.HUMAN:
        return CardKind.HUMAN
    return CardKind.WORK


def _gate_verdict_pass(metadata: Mapping[str, object]) -> bool:
    """Return True only if the gate metadata explicitly contains a pass verdict.

    Fail-secure: missing or malformed ``gate`` field is treated as FAIL (never PASS).
    See: plan.md §Security §Gate-verdict trust

    Args:
        metadata: CardResult metadata mapping.

    Returns:
        True if the gate explicitly passed, False otherwise.
    """
    gate = metadata.get(_GATE_VERDICT_KEY)
    return isinstance(gate, str) and gate.lower() == _GATE_PASS_VALUE


def launch_run(  # noqa: PLR0913
    *,
    spec_id: str,
    initial_context: Mapping[str, object],
    kanban: KanbanBoard,
    run_state: RunStateStore,
    serializer: DotSerializer,
    store: PipelineStore,
    clock: Clock,
) -> dict[str, object]:
    """Launch a new pipeline run from a given spec.

    Creates the first kanban card for the entry node (the node immediately
    after START), saves the Run and RunNode, and returns the run_id and status.

    Args:
        spec_id: The pipeline specification identifier.
        initial_context: Key/value context to seed the run with.
        kanban: The KanbanBoard port for creating cards.
        run_state: The RunStateStore port for persisting run state.
        serializer: The DotSerializer port for parsing the DOT source.
        store: The PipelineStore port for loading the DOT source.
        clock: The Clock port for timestamps.

    Returns:
        A dict with ``run_id`` (str) and ``status`` (str) keys.
    """
    now = clock.now()
    dot = store.load(spec_id)
    pipeline: Pipeline = serializer.parse(dot)
    ctx = Context(data=initial_context)
    run_id = str(uuid.uuid4())

    run = Run(
        run_id=run_id,
        spec_id=spec_id,
        status=RunStatus.RUNNING,
        context=ctx,
        created_at=now,
        updated_at=now,
    )
    run_state.create_run(run)

    # Find the first non-START node reachable from START.
    node_map = {n.node_id: n for n in pipeline.nodes}
    start_nodes = [n for n in pipeline.nodes if n.shape is NodeShape.START]
    if start_nodes:
        start_id = start_nodes[0].node_id
        # Get all edges from start; pick first target as entry node.
        start_edges = [e for e in pipeline.edges if e.source_id == start_id]
        first_edge = select_edge(start_edges, context=dict(ctx.data), routing_hint=None, suggested_nodes=[])
        if first_edge:
            entry_node = node_map.get(first_edge.target_id)
            if entry_node and entry_node.shape not in (NodeShape.START, NodeShape.EXIT):
                profile = pipeline.resolve_profile(entry_node) or ""
                prompt_template = entry_node.prompt or ""
                body = _expand_prompt(prompt_template, ctx.data)
                kind = _card_kind_for_node(entry_node.shape)
                key = IdempotencyKey.for_node(run_id, entry_node.node_id, 1)
                card = Card(
                    idempotency_key=key,
                    assignee_profile=profile,
                    body=body,
                    parent_task_ids=[],
                    retry_limit=entry_node.retry_limit,
                    kind=kind,
                )
                task_id = kanban.create_card(card)
                run_node = RunNode(
                    run_id=run_id,
                    node_id=entry_node.node_id,
                    task_id=task_id,
                    status=NodeRunStatus.DISPATCHED,
                    attempt=1,
                    parent_node_ids=[start_id],
                )
                run_state.upsert_node(run_node)

    return {"run_id": run_id, "status": run.status.value}


def advance_on_completion(  # noqa: PLR0912, PLR0915, C901
    *,
    card_result: CardResult,
    kanban: KanbanBoard,
    run_state: RunStateStore,
    pipeline: Pipeline,
    clock: Clock,
) -> None:
    """Advance the run state machine when a kanban card completes.

    Marks the completed node SUCCEEDED (or PARTIAL for a gate that failed),
    applies context updates, selects the next edge, creates follow-up cards,
    and saves the run with the updated event cursor (cursor-last ordering, FR-024).

    **HUMAN node behaviour (FR-013/FR-017)**:
    When the selected next node is a HUMAN node, this function creates a HUMAN
    card, calls ``block_card``, and persists the run as ``PAUSED_HUMAN``. The run
    then waits durably — **no busy-wait, no polling**. The ``PAUSED_HUMAN`` status
    is the durable persisted state; the run resumes only when the reconciler
    processes the human card's terminal completion event.

    **PAUSED_HUMAN resume**:
    When a HUMAN card's completion event is processed (run is ``PAUSED_HUMAN``),
    this function transitions the run back to ``RUNNING`` before the cursor-last
    ``save_run`` call.

    Args:
        card_result: The completion event from the kanban board.
        kanban: The KanbanBoard port for creating follow-up cards.
        run_state: The RunStateStore port for reading and persisting state.
        pipeline: The Pipeline domain object for traversal.
        clock: The Clock port for timestamps.
    """
    node_record = run_state.get_node_by_task(card_result.task_id)
    if node_record is None:
        _log.warning("advance_on_completion: no RunNode for task_id=%s", card_result.task_id)
        return

    run = run_state.get_run(node_record.run_id)
    if run is None:
        _log.warning("advance_on_completion: no Run for run_id=%s", node_record.run_id)
        return

    now = clock.now()
    node_map = {n.node_id: n for n in pipeline.nodes}
    pipeline_node = node_map.get(node_record.node_id)

    # Determine if this is a gate node and whether it passed.
    is_gate = pipeline_node is not None and pipeline_node.goal_gate is not None
    gate_passed = _gate_verdict_pass(card_result.metadata) if is_gate else True

    # Mark the completed node.
    completed_node = RunNode(
        run_id=node_record.run_id,
        node_id=node_record.node_id,
        task_id=node_record.task_id,
        status=NodeRunStatus.SUCCEEDED if gate_passed else NodeRunStatus.PARTIAL,
        attempt=node_record.attempt,
        parent_node_ids=node_record.parent_node_ids,
        goal_gate_policy=node_record.goal_gate_policy,
        output_ref=node_record.output_ref,
    )
    run_state.upsert_node(completed_node)

    # FAN_OUT: dispatch all outgoing branches as siblings.
    if pipeline_node is not None and pipeline_node.shape is NodeShape.FAN_OUT:
        fan_out_edges = [e for e in pipeline.edges if e.source_id == node_record.node_id]
        if len(fan_out_edges) > MAX_FAN_OUT_WIDTH:
            msg = f"FAN_OUT node '{node_record.node_id}' has {len(fan_out_edges)} branches; max is {MAX_FAN_OUT_WIDTH}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id=node_record.node_id, reason=msg)],
                message=msg,
            )
        for edge in fan_out_edges:
            branch_node = node_map.get(edge.target_id)
            if branch_node is None:
                continue
            branch_ctx = run.context.clone()
            branch_profile = pipeline.resolve_profile(branch_node) or ""
            branch_body = _expand_prompt(branch_node.prompt or "", branch_ctx.data)
            branch_key = IdempotencyKey.for_node(run.run_id, branch_node.node_id, 1)
            branch_card = Card(
                idempotency_key=branch_key,
                assignee_profile=branch_profile,
                body=branch_body,
                parent_task_ids=[card_result.task_id],
                retry_limit=branch_node.retry_limit,
                kind=_card_kind_for_node(branch_node.shape),
            )
            branch_task_id = kanban.create_card(branch_card)
            branch_run_node = RunNode(
                run_id=run.run_id,
                node_id=branch_node.node_id,
                task_id=branch_task_id,
                status=NodeRunStatus.DISPATCHED,
                attempt=1,
                parent_node_ids=[node_record.node_id],
            )
            run_state.upsert_node(branch_run_node)
        # Save run cursor after all branch dispatches (cursor-last).
        updated_run = Run(
            run_id=run.run_id,
            spec_id=run.spec_id,
            status=run.status,
            context=run.context,
            created_at=run.created_at,
            updated_at=now,
            root_task_id=run.root_task_id,
            last_seen_event_id=card_result.event_id,
        )
        run_state.save_run(updated_run)
        return

    # FAN_IN: check if all predecessor branches have completed before dispatching.
    # Select the next edge.
    routing_hint: str | None = "pass" if gate_passed else "fail"
    out_edges = [e for e in pipeline.edges if e.source_id == node_record.node_id]
    next_edge = select_edge(out_edges, context=dict(run.context.data), routing_hint=routing_hint, suggested_nodes=[])
    # When the next node is FAN_IN, only dispatch after all branches are done.
    #
    # BATCH-BOUNDARY SAFETY INVARIANT: each branch completion is a **durable write**
    # (``upsert_node`` sets the branch RunNode to SUCCEEDED before we query the
    # siblings). This means that even if a crash occurs mid-batch, re-processing
    # the event will re-query the sibling statuses and reach the same conclusion —
    # the FAN_IN check is idempotent and safe across reconciler batch boundaries.
    if next_edge:
        potential_fan_in = node_map.get(next_edge.target_id)
        if potential_fan_in is not None and potential_fan_in.shape is NodeShape.FAN_IN:
            # Find all predecessor nodes for this FAN_IN.
            fan_in_predecessors = {e.source_id for e in pipeline.edges if e.target_id == potential_fan_in.node_id}
            # Get all RunNodes for these predecessors.
            all_nodes = run_state.nodes_for_run(run.run_id)
            predecessor_nodes = [n for n in all_nodes if n.node_id in fan_in_predecessors]
            all_succeeded = all(
                n.status in (NodeRunStatus.SUCCEEDED, NodeRunStatus.PARTIAL) for n in predecessor_nodes
            ) and len(predecessor_nodes) == len(fan_in_predecessors)
            if not all_succeeded:
                # Not all branches done yet — just save cursor and return.
                updated_run = Run(
                    run_id=run.run_id,
                    spec_id=run.spec_id,
                    status=run.status,
                    context=run.context,
                    created_at=run.created_at,
                    updated_at=now,
                    root_task_id=run.root_task_id,
                    last_seen_event_id=card_result.event_id,
                )
                run_state.save_run(updated_run)
                return

    if next_edge:
        next_node = node_map.get(next_edge.target_id)
        if next_node and next_node.shape is NodeShape.HUMAN:
            # HUMAN node: create a HUMAN card, block it, and pause the run.
            profile = pipeline.resolve_profile(next_node) or ""
            prompt_template = next_node.prompt or ""
            body = _expand_prompt(prompt_template, run.context.data)
            attempt = node_record.attempt + 1 if next_node.node_id == node_record.node_id else 1
            key = IdempotencyKey.for_node(run.run_id, next_node.node_id, attempt)
            card = Card(
                idempotency_key=key,
                assignee_profile=profile,
                body=body,
                parent_task_ids=[card_result.task_id],
                retry_limit=next_node.retry_limit,
                kind=CardKind.HUMAN,
            )
            human_task_id = kanban.create_card(card)
            human_run_node = RunNode(
                run_id=run.run_id,
                node_id=next_node.node_id,
                task_id=human_task_id,
                status=NodeRunStatus.DISPATCHED,
                attempt=attempt,
                parent_node_ids=[node_record.node_id],
            )
            run_state.upsert_node(human_run_node)
            # Block the card and transition run to PAUSED_HUMAN (cursor-last).
            kanban.block_card(
                human_task_id,
                reason="Human input required",
                body=body,
            )
            paused_run = Run(
                run_id=run.run_id,
                spec_id=run.spec_id,
                status=RunStatus.PAUSED_HUMAN,
                context=run.context,
                created_at=run.created_at,
                updated_at=now,
                root_task_id=run.root_task_id,
                last_seen_event_id=card_result.event_id,
            )
            run_state.save_run(paused_run)
            return
        if next_node and next_node.shape is NodeShape.FAN_IN:
            # FAN_IN: dispatch the FAN_IN card (all predecessors already confirmed done above).
            fan_in_profile = pipeline.resolve_profile(next_node) or ""
            fan_in_key = IdempotencyKey.for_node(run.run_id, next_node.node_id, 1)
            fan_in_card = Card(
                idempotency_key=fan_in_key,
                assignee_profile=fan_in_profile,
                body=_expand_prompt(next_node.prompt or "", run.context.data),
                parent_task_ids=[card_result.task_id],
                retry_limit=next_node.retry_limit,
                kind=CardKind.WORK,
            )
            fan_in_task_id = kanban.create_card(fan_in_card)
            fan_in_run_node = RunNode(
                run_id=run.run_id,
                node_id=next_node.node_id,
                task_id=fan_in_task_id,
                status=NodeRunStatus.DISPATCHED,
                attempt=1,
                parent_node_ids=[node_record.node_id],
            )
            run_state.upsert_node(fan_in_run_node)
        elif next_node and next_node.shape not in (NodeShape.EXIT, NodeShape.HUMAN):
            profile = pipeline.resolve_profile(next_node) or ""
            prompt_template = next_node.prompt or ""
            body = _expand_prompt(prompt_template, run.context.data)
            kind = _card_kind_for_node(next_node.shape)
            attempt = node_record.attempt + 1 if next_node.node_id == node_record.node_id else 1
            key = IdempotencyKey.for_node(run.run_id, next_node.node_id, attempt)
            card = Card(
                idempotency_key=key,
                assignee_profile=profile,
                body=body,
                parent_task_ids=[card_result.task_id],
                retry_limit=next_node.retry_limit,
                kind=kind,
            )
            next_task_id = kanban.create_card(card)
            next_run_node = RunNode(
                run_id=run.run_id,
                node_id=next_node.node_id,
                task_id=next_task_id,
                status=NodeRunStatus.DISPATCHED,
                attempt=attempt,
                parent_node_ids=[node_record.node_id],
            )
            run_state.upsert_node(next_run_node)
        elif next_node and next_node.shape is NodeShape.EXIT:
            # Run has reached the EXIT node — mark as SUCCEEDED.
            finished_run = Run(
                run_id=run.run_id,
                spec_id=run.spec_id,
                status=RunStatus.SUCCEEDED,
                context=run.context,
                created_at=run.created_at,
                updated_at=now,
                root_task_id=run.root_task_id,
                last_seen_event_id=card_result.event_id,
            )
            run_state.save_run(finished_run)
            return

    # Save run with updated cursor LAST (FR-024 cursor-last ordering).
    # Transition PAUSED_HUMAN -> RUNNING when resuming from a completed human card.
    new_status = RunStatus.RUNNING if run.status is RunStatus.PAUSED_HUMAN else run.status
    updated_run = Run(
        run_id=run.run_id,
        spec_id=run.spec_id,
        status=new_status,
        context=run.context,
        created_at=run.created_at,
        updated_at=now,
        root_task_id=run.root_task_id,
        last_seen_event_id=card_result.event_id,
    )
    run_state.save_run(updated_run)
