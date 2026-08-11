# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **`--vault-repo`** — `solaris init --obsidian --vault-repo` creates a sibling Obsidian vault git repo (tag-along) + `solaris.toml` in the code repo
- **Solaris Kanban Fix** plugin in Obsidian seed — retries Bases `kanban` registration; docs: `docs/obsidian-kanban.md`
- Welcome + init CLI checklist for **Restricted mode** (must be turned off once per vault)

### Changed

- Obsidian seed: vendored Base Board refreshed; `community-plugins.json` enables Base Board + Solaris Kanban Fix

## [0.1.6] — 2026-08-05

### Added

- **Tag-along binding** — `solaris.toml` / `.solaris/config.toml` + vault `linked_repos`; `resolve_board_root()`; `solaris doctor`
- **`solaris init --link`** — install Cursor gate into a code repo; vendors `.cursor/lib/` so system Python need not `pip install solaris`
- Agent gate **v2.1** — workspace ≠ `board_root`; per-repo session under code `.cursor/`; soft `require_prd` (default false)
- Resilient Cursor hook — import/runtime failures **fail open** (never deadlock the agent); intentional denies still block

### Changed

- Docs: planes (Solaris = work/record, not memory); tag-along gate section in `docs/agents.md` / `AGENT-CONTEXT.md`

## [0.1.5] — 2026-08-01

### Added

- `solaris init --obsidian` scaffolds `.obsidian/` with **Bases** (core), **Base Board** plugin, and **Nebula** theme
- README: how to install the Obsidian desktop app (macOS / Windows / Linux)

## [0.1.4] — 2026-08-01

### Changed

- `active_sprint` lives on `<board_dir>/Sprints/index.md` (removed `Sprint.md`)

### Added

- **Weekly Home sprint rollover** — archives closed week to `<board_dir>/Sprints/MM-DD-YYYY/home.md` with plan/goals/retro stubs; patches Home Done filter to `active_sprint`; `--seed-current` for first-time week folder

### Changed

- `solaris rollover` marks carry on unfinished sprint lanes and seeds the new week folder
- `Home.core.base` Home/Flow views filter Done by current sprint week

## [0.1.3] — 2026-08-01

### Added

- **`board_dir`** — board folder defaults to host repo basename on `solaris init` (override with `--board-dir` or `board_dir:` in config)
- Init scaffolds `Wiki/`, `Notes/`, `Welcome.md`, `To Do.md`; Agents under `<board_dir>/Agents/` with Agents Dashboard + Agent work embed; Dashboard WTFAQs

### Changed

- Discovery finds `<basename>/config.yml`, `Board/config.yml`, or `board.config.yml`
- Dropped human `Templates/` and `Board/Projects/` from init (wiki hubs at `Wiki/<Project>/index.md`)
- Humans how-to lives in Dashboard **WTFAQs** (no root `Humans.md`)

## [0.1.2] — 2026-08-01

### Added

- **Agent board gate** (`solaris.agent_gate`): Cursor hooks block mutations until rules read + register + plan + session-bind + todos
- CLI: `solaris agent gate-status|session-bind|session-unbind`
- Session bind on `plan-open` / clear on `plan-close`; dry-run via `BOARD_GATE_DRY_RUN` or `.cursor/agent-gate-config.json`
- `solaris init` installs `.cursor/hooks.json` + gate hook; Hermes preflight note in `INSTANCE.md`

## [0.1.1] — 2026-08-01

### Added

- Persistent **agent registry** + Agent Dashboard (`solaris agent register|plan-open|plan-close|dashboard`)
- Plan ledger under wiki `Plans/` with self-reported LOC/PR metrics on close
- `agent_id` / `plan_id` on tasks; registry gate when `features.agent_registry` is on
- Obsidian views: **Agent work**, **By agent**; kanban file renamed to `Home.base`

### Changed

- `solaris init` writes `Board/Home.base` (was `Board.base`) and scaffolds `Board/Agents/`

## [0.1.0] — 2026-07-30

### Added

- Initial public release of **Solaris** board engine
- CLI: `init`, `task` (create/move/edit/list), `export`, `sync`, `rollover`, `rollup`
- Seven-lane model with triage; agent and roadmap-sync sources skip triage
- Safe sprint rollover with ISO week gap guard and feature flags
- Initiative progress rollup (owned `progress_*` keys only)
- Obsidian Base skeleton + human/agent documentation seeds
- Portable instance scaffold (`Board/`) for vault or bare git repo
