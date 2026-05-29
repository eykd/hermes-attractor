"""RunStateStore port: durable state for pipeline Run and RunNode entities.

See: specs/001-attractor-kanban/contracts/ports.md §RunStateStore
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hermes_attractor.domain.run import Run, RunNode


class RunStateStore(Protocol):  # pragma: no cover
    """Port for creating, reading, and updating Run and RunNode state (research D6).

    Implementations persist to ``plugin_runs`` / ``plugin_run_nodes`` tables.

    Contract notes:
        ``save_run`` persisting ``last_seen_event_id`` MUST be the **last** write
        of a successful advancement so a crash mid-advance re-processes the event
        (idempotent replay, FR-024).
    """

    def create_run(self, run: Run) -> None:
        """Insert a new Run record.

        Args:
            run: The Run to persist.
        """
        ...

    def get_run(self, run_id: str) -> Run | None:
        """Fetch a Run by its run_id.

        Args:
            run_id: The unique run identifier.

        Returns:
            The Run if found, else ``None``.
        """
        ...

    def active_runs(self) -> Sequence[Run]:
        """Return all Runs in RUNNING or PAUSED_HUMAN status.

        Returns:
            A sequence of active Run records.
        """
        ...

    def save_run(self, run: Run) -> None:
        """Update an existing Run (including last_seen_event_id cursor).

        This MUST be the last write of a successful advancement step so that
        a mid-advance crash causes the event to be re-processed on replay.

        Args:
            run: The updated Run to persist.
        """
        ...

    def upsert_node(self, node: RunNode) -> None:
        """Create or update a RunNode (keyed on run_id + node_id + attempt).

        Args:
            node: The RunNode to create or update.
        """
        ...

    def get_node_by_task(self, task_id: str) -> RunNode | None:
        """Fetch the RunNode associated with a given kanban task_id.

        Args:
            task_id: The kanban task identifier.

        Returns:
            The RunNode if found, else ``None``.
        """
        ...

    def nodes_for_run(self, run_id: str) -> Sequence[RunNode]:
        """Return all RunNode records for a given run_id.

        Args:
            run_id: The run identifier.

        Returns:
            A sequence of RunNode records for the run, possibly empty.
        """
        ...
