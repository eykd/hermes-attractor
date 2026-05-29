"""Domain-level constants for hermes_attractor.

These values are load-bearing constraints referenced by the domain and use-case
layers. Do not import from adapters or plugin here — this module has zero external
dependencies.
"""

from __future__ import annotations

#: Maximum allowed length (in characters) of a guard expression string (FR-011).
MAX_GUARD_LENGTH: int = 512

#: Maximum allowed nesting depth for the guard recursive-descent parser (FR-011).
#: Exceeding this raises PipelineValidationError at parse time, never a RecursionError.
MAX_GUARD_DEPTH: int = 32

#: Maximum fan-out width: number of concurrent branches spawned by a FAN_OUT node.
MAX_FAN_OUT_WIDTH: int = 16

#: Maximum number of live kanban cards per run at any given time (FR-016).
MAX_LIVE_CARDS_PER_RUN: int = 256

#: Batch size for reading events from the EventLog (research D6).
EVENT_LOG_BATCH_SIZE: int = 100

#: Maximum raw DOT input size in bytes for DotSerializer.parse (resource limit).
DOT_MAX_INPUT_BYTES: int = 1_048_576  # 1 MiB

#: Maximum number of nodes allowed in a parsed pipeline graph (resource limit).
DOT_MAX_NODES: int = 256

#: Maximum number of edges allowed in a parsed pipeline graph (resource limit).
DOT_MAX_EDGES: int = 1024
