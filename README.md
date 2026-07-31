<p align="center">
  <h1 align="center">Solaris</h1>
  <p align="center">
    <strong>Markdown-native project board for humans and AI agents</strong><br/>
    Local-first · Git-friendly · Obsidian-ready · Zero SaaS
  </p>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="docs/humans.md">Humans</a> ·
  <a href="docs/agents.md">Agents</a> ·
  <a href="docs/safety.md">Safety</a>
</p>

---

> **Solaris** turns any folder or git repo into a self-contained project board.
> Tasks are plain Markdown. Agents create tickets and move them as they work.
> You approve the plan once — not every card.

Inspired by the best ideas in [Linear](https://linear.app) (triage, cycles, health),
[Plane](https://plane.so) (intake, initiatives), and [Backlog.md](https://github.com/MrLesk/Backlog.md)
(acceptance criteria + agent ledger) — without their runtimes or lock-in.

## Why Solaris

| Problem | Solaris |
|---------|---------|
| PM tools live in someone else's cloud | Files in **your** repo / vault |
| Agents drown you in untracked work | Automatic ticket ledger + live lanes |
| Humans can't review thousands of tickets | Approve the **plan** once; board is a log |
| Obsidian boards aren't portable | Same schema works in a bare git repo |

## Install

```bash
pip install git+https://github.com/DevMandalia/solaris-board.git

# or from a local clone
pip install -e .

# CLI: solaris-board   (or: python -m solaris)
```

Requires Python 3.10+.

## Quick start

```bash
# In any project directory
solaris-board init --name MyApp --project Eng
export BOARD_ROOT=$PWD

solaris-board task create --title "Add auth" --project Eng --build \
  --lane "doing this week" --phase mvp
solaris-board task move add-auth --lane "in progress now"
# ... do the work ...
solaris-board task move add-auth --lane done

solaris-board export --include-done
```

### Vault mode (Obsidian)

`solaris-board init` writes `Board/Board.base`, templates, Dashboard, and agent docs.
Open the folder as an Obsidian vault (or add `Board/` to an existing vault) and use the Flow / Triage views.

### Repo mode (no Obsidian)

Use the CLI only. Commit `Board/` with your code. `solaris-board export` prints a markdown kanban for PRs and status updates.

## How it works

```
Board/
  config.yml           # instance: projects, feature flags
  Tasks/<Project>/     # one .md file per task
  Projects/            # project hubs
  Sprint.md            # active ISO week
  _system/             # portable schema + templates (vendored on init)
  Humans.md            # human operating manual
```

**Lanes:** `triage` → `backlog` → `doing this week` → `in progress now` → `blocked` → `done` / `archived`

| Source | Triage? |
|--------|---------|
| Human / intake | Yes |
| `source: agent` | Never |
| `source: roadmap-sync` | Never |

## Agent loop (automatic)

1. You approve a multi-step plan (“execute”).
2. Agent runs `solaris-board task create` for each unit (`source: agent`).
3. As it works: `move` → `in progress now` → `done`.
4. History = task files + git. No per-ticket human gate.

See [docs/agents.md](docs/agents.md).

## Humans

Daily triage, weekly planning/review, WIP — [docs/humans.md](docs/humans.md).

## Safety

- Sprint rollover **aborts** if the ISO week gap is larger than configured (no mass-carry disasters).
- Feature flags default conservative (`sprint_rollover` / `initiative_rollup` off until you enable them).
- Rollup writes only `progress_*` keys — never initiative body or health.

Details: [docs/safety.md](docs/safety.md).

## CLI reference

```
solaris-board init [--root DIR] [--name NAME] [--project NAME] [--force]
solaris-board task create --title T --project P [--build] [--lane L] [--phase X]
solaris-board task move <slug|path> --lane LANE
solaris-board task edit <slug|path> [--plan ...] [--append-log ...]
solaris-board task list [--lane L] [--phase X] [--project P]
solaris-board export [-o file.md] [--include-done] [--include-archived]
solaris-board sync
solaris-board rollover [--dry-run] [--force]
solaris-board rollup [--dry-run] [--force]
```

Global: `solaris-board --cwd DIR ...` or `export BOARD_ROOT=/path/to/instance`.

## Concepts

| Concept | Meaning |
|---------|---------|
| **Project** | Top-level area (folder under `Board/Tasks/`) |
| **Initiative** | Multi-step effort with optional wiki hub + health |
| **Task** | One board card = one Markdown file |
| **Lane** | Kanban column (status of work) |
| **Phase** | Label linking a batch of agent tickets |

## Development

```bash
git clone https://github.com/DevMandalia/solaris-board.git
cd solaris-board
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).

## Related

This engine was extracted from a personal vault workflow and designed so **system ≠ content**:
the core ships here; your tasks, projects, and wikis stay in your instance.
