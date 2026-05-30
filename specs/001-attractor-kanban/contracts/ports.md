# Contract: Port Protocols

**Branch**: `001-attractor-kanban` | **Layer**: `src/hermes_attractor/ports/`

Ports are `typing.Protocol`s (coverage-omitted). The domain and use_cases depend on these;
adapters implement them. Only `plugin/` and adapters know Hermes/SQLite/git/pydot. All
signatures are illustrative contracts to be encoded in Phase implementation (RED first).

## `ports/kanban.py` — `KanbanBoard`

Isolates every kanban tool/REST call (research risk R2 lives entirely here).

```python
class KanbanBoard(Protocol):
    def create_card(self, card: Card) -> str:
        """Create (or dedupe via idempotency_key) a kanban card; return its task_id."""

    def block_card(self, task_id: str, *, reason: str, body: str) -> None:
        """Block a card awaiting human action (human-in-the-loop pause)."""

    def complete_card(self, task_id: str, *, summary: str,
                      metadata: Mapping[str, object]) -> None:
        """Mark a card complete with a structured result (used by tool nodes)."""
```

*Contract notes*: `create_card` MUST pass `card.idempotency_key.value` so re-creation is a
no-op returning the existing non-archived task id (research D5, FR-024). Implementations
MUST NOT raise on a duplicate key — they return the existing id.

## `ports/event_log.py` — `EventLog`

Tails the durable kanban `task_events` log for the reconciler (research D2/D6).

```python
class EventLog(Protocol):
    def read_since(self, last_seen_event_id: int) -> Sequence[CardResult]:
        """Return terminal completion events with id > last_seen_event_id, ordered by id.
        Terminal kinds only: completed, blocked, gave_up, crashed, timed_out."""
```

## `ports/pipeline_store.py` — `PipelineStore`

Git-tracked `.dot` file storage with local-only fallback (FR-003).

```python
class PipelineStore(Protocol):
    def load(self, spec_id: str) -> str:               # raw DOT text
    def save(self, spec_id: str, dot: str) -> None:    # writes + git-tracks the .dot
    def ensure_repo(self) -> None:                     # init local-only repo if absent
```

## `ports/dot.py` — `DotSerializer`

DOT (de)serialization (research R-DOT). Keeps `pydot` out of the domain.

```python
class DotSerializer(Protocol):
    def parse(self, dot: str) -> Pipeline:   # raises DotParseError on malformed DOT
    def emit(self, pipeline: Pipeline) -> str:
```

*Contract notes*: round-trip `emit(parse(x))` MUST be structurally stable. Attractor
attribute names / status enums are reconciled against the Attractor NLSpec here, not in the
domain.

## `ports/run_state.py` — `RunStateStore`

Plugin-owned durable state (research D6). Maps `Run`/`RunNode` to `plugin_runs` /
`plugin_run_nodes`.

```python
class RunStateStore(Protocol):
    def create_run(self, run: Run) -> None
    def get_run(self, run_id: str) -> Run | None
    def active_runs(self) -> Sequence[Run]
    def save_run(self, run: Run) -> None                  # incl. last_seen_event_id cursor
    def upsert_node(self, node: RunNode) -> None
    def get_node_by_task(self, task_id: str) -> RunNode | None
    def nodes_for_run(self, run_id: str) -> Sequence[RunNode]
```

*Contract notes*: `save_run` persisting `last_seen_event_id` MUST be the **last** write of
a successful advancement so a crash mid-advance re-processes the event (idempotent replay,
FR-024).

## `ports/renderer.py` — `Renderer`

Human-readable summary/visualization (FR-005, research R-RENDER).

```python
class Renderer(Protocol):
    def summarize(self, pipeline: Pipeline) -> str:   # pure-Python text summary
```

## `ports/tool_node.py` — `ToolNodeRegistry`

Resolves a TOOL node's deterministic work (FR-012).

```python
class ToolNodeRegistry(Protocol):
    def run(self, tool_name: str, context: Context) -> Outcome:
        """Invoke deterministic (non-agent) work; return context updates as an Outcome."""
```

## `ports/clock.py` — `Clock` (existing)

Reused for `created_at` / `updated_at` timestamps; no change to the existing port shape.

## `ports/hermes.py` — `PluginContext` (existing, extended)

The registration surface. Extend the existing Protocol to register hooks and a CLI command
in addition to tools (research D2):

```python
class PluginContext(Protocol):
    def register_tool(self, *, name: str, schema: dict[str, object],
                      handler: ToolHandler) -> None: ...
    def register_hook(self, *, event: str, handler: HookHandler) -> None: ...   # post_tool_call
    def register_command(self, *, name: str, handler: CommandHandler) -> None:  # reconcile
        ...
```

*Contract notes*: hook/command registration shapes are **UNVERIFIED** against the installed
Hermes runtime (entry-point group `hermes_agent.plugins`, research R-EP). The Protocol
encodes the assumed surface so the core stays decoupled; reconcile at implementation.
