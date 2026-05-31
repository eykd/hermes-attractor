# hermes-attractor Development Conventions

## What this is

`hermes-attractor` is a **Hermes Agent plugin** (`attractor`) built on a hexagonal core.
The plugin's real logic lives in `src/hermes_attractor/` as pure Python; the Hermes
runtime coupling is isolated to a thin `plugin/` shim. It ships via a pip entry point
(`hermes_agent.plugins` group) and is symlinked into `.hermes/plugins/attractor` for local dev.

## Active Technologies

- **Language**: Python 3.11 (pinned via `.python-version`; `requires-python = ">=3.11,<3.12"`)
- **Package/Env manager**: `uv`
- **Linting/format**: `ruff` (120-char line length, `py311` target)
- **Type checking**: `pyright` in **strict mode** + paranoid escalations (run `uv run pyright`)
- **Testing**: `pytest` with a **100% coverage** requirement (branch coverage on)
- **Pre-commit**: ruff, ruff-format, pyright, pytest (100%) — never bypass
- **Tasks**: `br` (beads) — task graph in `.beads/` (git-tracked)

## Architecture

Hexagonal (ports & adapters). Dependencies point inward: `domain ← use_cases`,
`use_cases → ports`, `adapters → ports`, and only `plugin/` knows about Hermes.

```
plugin.yaml          # Root manifest read by `hermes plugins install` (git path)
__init__.py          # Root shim: add src/ to sys.path, re-export register (git path only)
src/hermes_attractor/
├── domain/      # Entities, value objects, exceptions. ZERO external deps. Pure rules.
├── ports/       # Protocols / interfaces (coverage-omitted). Contracts for the outside.
├── adapters/    # Concrete implementations of ports (system clock, I/O, clients).
├── use_cases/   # Application orchestration over domain + ports.
└── plugin/      # Hermes entry shim — the ONLY Hermes-coupled layer.
    ├── __init__.py   # register(ctx): wires schemas/handlers + hooks + CLI command
    ├── schemas.py    # LLM-facing tool JSON schemas
    ├── tools.py      # Handlers: call use_cases, return a JSON string, NEVER raise
    └── reconcile.py  # on_session_start / post_tool_call hooks + attractor-reconcile CLI
```

The two **root** files (`plugin.yaml`, `__init__.py`) exist only for the `hermes plugins install`
(git/directory) load path; the pip entry-point path uses neither.

**The `plugin/tools.py` contract**: every handler takes parsed tool input, **always
returns a JSON string, and never raises** (it catches `Exception` and returns an error
payload). This is why `tools.py` carries a targeted ruff per-file-ignore (`BLE001`,
`ARG001`). Keep handlers thin — delegate real work to `use_cases`.

## Code Conventions

- **Imports**: absolute from the package root, e.g. `from hermes_attractor.domain.exceptions import AttractorError`.
- **Type hints**: complete and strict. Type-only imports go under `if TYPE_CHECKING:`
  (enforced by ruff `TC`). Use `# pyright: ignore[reportX]` (not `# type: ignore`) when a
  suppression is genuinely needed — `reportUnnecessaryTypeIgnoreComment` is an error.
- **Errors**: raise domain exceptions from `hermes_attractor.domain.exceptions`
  (`AttractorError` base). Use `msg = "..."; raise XError(msg)` (ruff `EM`).
- **Docstrings**: Google style; module/class/function docstrings required (ruff `D`).
- **No `print`** in library code (ruff `T20`); use `logging`.

## Quality gate (always)

`ruff check` + `ruff format --check` + `uv run pyright` (strict) + `uv run pytest` (100%).
Enforced in pre-commit AND via PostToolUse hooks after every Edit/Write. **Never** use
`--no-verify` / `--no-gpg-sign`; fix the underlying issue.

```bash
just install   # uv sync --all-groups
just lint       # ruff check + ruff format --check + pyright
just format     # ruff format + ruff check --fix
just test       # pytest at 100% coverage
just ci         # lint + test
just hooks      # install pre-commit hooks
```

## Development workflow

This repo uses the spec-kit (`sp/`) phases, the `ralph` in-session orchestrator, and
beads, all wired through the `.claude/` harness.

- **Spec-kit**: `/sp:next` advances the workflow; phases run constitution → brainstorm →
  specify → plan → red-team → tasks → analyze → implement → harden. Tasks land in beads.
- **ralph**: `/ralph` drains the beads ready-queue, dispatching prep → worker → verify
  per task within the session.
- **TDD loop**: RED (write a failing test via `/pytest-*` or `/test-driven-development`)
  → GREEN (minimal code; use `/prefactoring` first) → REFACTOR (use `/refactoring`,
  keep 100% coverage) → commit (`/commit`).

### Required skill usage
- **`/prefactoring`** when designing modules, types, or APIs.
- **`/ddd-domain-modeling`** when building the domain layer (entities, value objects, ports).
- **`/refactoring`** during the REFACTOR step.
- **`/error-handling-patterns`** when designing exception hierarchies / safe responses.
- **`/architecture-review`** to validate hexagonal boundaries before merging.

## Beads task tracking (`br`)

```bash
br ready                 # tasks ready to work (no blockers)
br list                  # all tasks
br create "Task"         # create a task
br show <id>             # task details
br close <id>            # close a completed task
br dep <id> blocks <id>  # add a dependency
br sync --flush-only     # flush state to .beads/ (git-friendly JSONL)
```

The `.beads/` directory is git-tracked.

## Hermes runtime integration (verified against `hermes-agent==0.15.2`)

`hermes-agent` is a **test dependency** (the `test` dependency-group, pinned `>=0.15.2`;
latest == 0.15.2). It is **not** a runtime dependency — the plugin's runtime gets
`hermes_cli` / `tools` from the host; the test group only installs it so the live
integration suite runs as part of the normal gate (`just test`, hermetic temp `HERMES_HOME`,
no model key). `just test-hermes` runs just the integration subset.

- `register(ctx)` on the real `hermes_cli.plugins.PluginContext` registers all 13 tools, two
  reconcile hooks — `post_tool_call` (primary, low-latency: advance inline when a worker
  completes a card) and `on_session_start` (recovery: replay missed completions) — and the
  `attractor-reconcile` CLI command. The `ports/hermes.py::PluginContext` signatures mirror 0.15.2.
- Both advancement paths reuse the idempotent `run_reconcile` (cursor-based, no double advance),
  driven via the verified `tools.registry.registry.dispatch(name, args)` seam
  (`adapters/runtime_tool_client.py`) and the kanban `task_events` log read directly from the
  DB (`adapters/task_event_reader.py`); see `specs/001-attractor-kanban/research-hermes-kanban.md`
  §Phase 1 for the verified tool names/params/schema. `post_tool_call` is gated to
  `kanban_complete`; other terminal kinds (blocked/crashed/timed_out/gave_up) are handled by the
  recovery path.
- Run-launch rejects pipelines naming a profile absent from the host (FR-004 / unknown-profile
  edge case): `launch_run` takes a `ProfileRegistry`; `adapters/profile_registry.py::HermesProfileRegistry`
  wraps `hermes_cli.profiles.profile_exists` (`default` always exists; others ⇒
  `HERMES_HOME/profiles/<name>/`). The escape hatch is the `attractor_provision_profiles` tool —
  it creates a pipeline's missing profiles (`use_cases/provisioning.py` over
  `adapters/profile_provisioner.py::HermesProfileProvisioner` → `create_profile(clone_config=True)`),
  cloning the active profile so each new profile gets a working model. Differentiate models afterward
  by editing each `HERMES_HOME/profiles/<name>/config.yaml` `model.default`.
- All `hermes_cli` / `tools.registry` imports are **lazy** (inside functions, via `importlib`),
  so production modules import cleanly without the package as a runtime dep and pyright (run in
  the locked env) does not statically resolve them. The runtime entry points (`post_tool_call_hook`,
  `reconcile_hook`, `attractor-reconcile` handler, `_runtime_*` builders, `HermesProfileRegistry`)
  are covered end-to-end by the integration suite — no `# pragma: no cover` on hermes seams.

**Install path = pip entry point.** Hermes's loader does `ep.load()` then
`getattr(module, "register")`, so the `hermes_agent.plugins` entry point references the **module**
(`hermes_attractor.plugin`, not `:register`) — a contract test (`tests/contract/test_entry_point.py`)
guards this. Install by `pip install`-ing the package into the hermes env (e.g. one Dockerfile
line); pip resolves `pydot` and hatch-vcs generates `_version.py` at build time.

The git-based `hermes plugins install <repo>` path is **not supported** for this plugin: it clones
the repo, expects `plugin.yaml` + a `register`-exposing `__init__.py` at the **repo root** (ours are
under `src/hermes_attractor/plugin/`), and **installs no dependencies** — so the real `pydot` dep
(and the gitignored, build-generated `_version.py`) would fail at load. Supporting it would need a
root shim + `_version` guard + lazy `pydot`, and *still* require `pydot` server-side — at which point
the pip path is strictly simpler.

Still **unverified** (no live `hermes` session here): end-to-end *discovery + register* inside a
running gateway (the suite verifies the entry point resolves + `register(ctx)` on a real
`PluginContext`, but not the two composed in a live load).

## Meta-conventions

- **Do NOT** track the active tech stack as a changelog here — update only on genuine change.
- **Do NOT** record recent changes in CLAUDE.md; it is for conventions, not history.
