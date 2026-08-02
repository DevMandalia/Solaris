---
type: meta
title: Board PM core — agent context
schema_version: 2
audience: agents
scope: portable board system (no instance content)
stability: changes when core board model changes
---

# Board PM core — agent context

Portable markdown project board for humans and AI agents.  
**Instance overlay** (projects, capture, cron): read `Board/INSTANCE.md` after this file.

Tools: `Board/_system/tools/` · Config: `Board/config.yml` · Set `BOARD_ROOT` if not auto-discovered.  
Safety rails: [[Board/_system/SAFETY]] (gap guard, source→lane rules, rollup write scope, feature flags).

---

## TL;DR

1. **Hierarchy:** Project → optional Initiative → Task (flat files under `Board/Tasks/<folder>/`).
2. **Lanes:** `triage` → `backlog` → `doing this week` → `in progress now` → `blocked` → `done` / `archived`.
3. **`done` = shipped.** **`archived` = withdrawn** (not shipped).
4. **Register before code** — persistent profile in `Board/Agents/<agent_id>.md` (see Agents Dashboard).
5. **Plan before implement** — open a plan ledger + wiki plan; file tasks with `agent_id` + `plan_id`.
6. **Mutate tasks via CLI** — `board_task.py` create/move/edit — do not hand-edit YAML frontmatter.
7. **Agent execution is automatic** after the user accepts a plan: create tickets, move lanes, no per-ticket human gate.
8. **`source: agent`** tickets never use `triage`. **`source: roadmap-sync`** never uses `triage`.
9. **Close the plan** with self-reported `--lines-added` / `--lines-removed` / `--prs`.

---

## Session start checklist

Run before the first file edit in a session (skip only for pure Q&A / no mutations):

```bash
export BOARD_ROOT=<vault-root>   # e.g. ~/MyVault
solaris agent list
solaris agent list --plans --open
```

| Check | Action if missing |
|-------|-------------------|
| Agent profile exists | `solaris agent register --id … --name … --model … --owner …` |
| Open plan for this work | `solaris agent plan-open --agent … --title … --project …` |
| Session bound | Auto on `plan-open`, or `solaris agent session-bind --plan-id …` |
| Tasks filed | `solaris task create … --agent … --plan-id …` for each unit |
| Gate ready | `solaris agent gate-status` (exit 0) |
| Ready to code | Move first task → `in progress now`, then edit files |

### Cursor gate (enforced)

Project hook: `.cursor/hooks/agent-board-gate.py` via `.cursor/hooks.json` (`failClosed` on mutate).

Bootstrap-only writes before ready: `Board/Agents/*.md`, `**/Plans/**`, `Board/Tasks/**`, Agents Dashboard, `.cursor` gate state. Obsidian workspace noise is always allowed.

Dry-run: `BOARD_GATE_DRY_RUN=1` or `.cursor/agent-gate-config.json` `{"dry_run": true}`.

Visibility: [[Board/Agents Dashboard]] · [[Board/Home.base#Agent work]]

---

## Lanes

| Lane | Meaning |
|------|---------|
| **triage** | Human/intake inbox — not yet accepted into the backlog |
| **backlog** | Prioritized pool (lower `kanban_order` = higher) |
| **doing this week** | Committed to active sprint, not started |
| **in progress now** | Active work |
| **blocked** | Waiting — set `blocked_reason` |
| **done** | Shipped |
| **archived** | Cancelled / withdrawn |

---

## Agent execution loop (automatic)

**Before any code or file edits in the workspace:**

1. **Register** (once per persistent agent) or confirm `Board/Agents/<agent_id>.md` exists.
2. **Human gate (once):** user approves the plan / says execute.
3. **`plan-open`** — creates a plan under `Wiki/<Project>/Plans/` or `Wiki/<Project>/Initiatives/<id>/Plans/`.
4. **File tasks** with `--agent` and `--plan-id` (`source: agent`, never triage).
5. **Execute** — no per-ticket human gate. Watch progress on `Home.base` → **Agent work**.
6. **`plan-close`** — self-report LOC/PRs; rollups update Agent Dashboard.

While executing:

1. One task per concrete work unit (`board_task.py create --source agent --build --agent … --plan-id …`).
2. Prefer `lane: doing this week`; put the active unit in `in progress now`.
3. `move --lane "in progress now"` → implement → Log / Final Summary → `move --lane done`.
4. New work discovered → create another agent task (same `plan_id`); do not silently expand scope.
5. True external wait → `blocked` + reason.

History lives in agent profiles, plan ledgers, task files, wiki plans, and git.

**Skip tickets** for trivial one-shot asks. **Always file tickets** for multi-step plan execution that touches code.

Visibility: `Board/Agents Dashboard.md` · `Home.base` → **Agent work** / **By agent**.

---

## CLI

```bash
export BOARD_ROOT=/path/to/instance   # optional if cwd/config discoverable

python3 Board/_system/tools/board_agent.py register \
  --id my-agent --name "My Agent" --model "model-id" --owner "Your Name"

python3 Board/_system/tools/board_agent.py plan-open \
  --agent my-agent --title "Ship feature X" --project "Acme" \
  --initiative-id in_foo

python3 Board/_system/tools/board_task.py create \
  --title "Extract portable core" --project "Acme" --build \
  --agent my-agent --plan-id <plan_id> \
  --phase my-initiative --lane "doing this week"

python3 Board/_system/tools/board_task.py move <slug-or-path> --lane "in progress now"
python3 Board/_system/tools/board_task.py move <slug-or-path> --lane done
python3 Board/_system/tools/board_task.py list --agent my-agent --plan-id <plan_id>

python3 Board/_system/tools/board_agent.py plan-close <plan_id> \
  --lines-added 120 --lines-removed 15 --prs 1

python3 Board/_system/tools/board_agent.py dashboard
python3 Board/_system/tools/board_export.py
python3 Board/_system/tools/board_sprint_rollover.py --dry-run
python3 Board/_system/tools/board_initiative_rollup.py --dry-run
```

---

## Task frontmatter (core)

| Property | Required | Notes |
|----------|----------|-------|
| `type` | yes | `task` |
| `title` | yes | |
| `project` | yes | Must match `config.yml` project name |
| `domain` | yes | From config or override |
| `lane` | yes | One of seven lanes |
| `source` | yes | `board` · `agent` · `roadmap-sync` · instance-specific |
| `priority` | no | P0–P3 tag only (not a column) |
| `kanban_order` | no | Sort within lane |
| `sprint` | no | ISO week — synced from sprint lanes |
| `carry` | no | Rolled from prior sprint |
| `phase` | no | Batch / epic label |
| `initiative_id` | no | Links to initiative hub |
| `roadmap_id` | no | When `source: roadmap-sync` |
| `agent_id` | yes if `source: agent` + registry on | Registered agent profile |
| `plan_id` | yes if `source: agent` + registry on | Open plan ledger id |
| `blocked_reason` | no | When blocked |

Build body sections: Context, Acceptance Criteria, Implementation Plan, Subtasks, Final Summary, Log.

---

## Initiative frontmatter (core)

`type: initiative`, `initiative_id`, `project`, `title`, `status` (`active`|`paused`|`archived`), optional:

- `health`: `on_track` | `at_risk` | `off_track` | `unknown` (human-set)
- `health_updated`: date
- `progress_done` / `progress_open` / `progress_blocked` (tool-owned)

Rollup tools must never overwrite `health` or initiative body Status sections.

---

## Triage leave rules (humans / intake adapters)

1. Accept → `backlog` (or a sprint lane); require `project` + `priority`.
2. Reject → `archived`.
3. Default Flow views exclude `triage`.

---

## Sprint rollover

`board_sprint_rollover.py` bumps `Board/Sprint.md` and sets `carry: true` on unfinished sprint-lane tasks.  
Aborts if ISO week gap > `rollover.max_week_gap` unless `--force`. Feature flag defaults off until the instance sets a correct `active_sprint`.

---

## Anti-patterns

| Avoid | Instead |
|-------|---------|
| Touch code before registering | `board_agent.py register` |
| Implement without a plan ledger | `plan-open` + wiki plan + tasks |
| Hand-edit task YAML | `board_task.py` |
| Put `source: agent` in triage | `doing this week` / `in progress now` |
| Put roadmap-sync in triage | Always backlog (+ lane drag) |
| Wait for human on every ticket | Auto-move after plan approval |
| `lane: done` for cancelled work | `archived` |
| Write health from rollup scripts | Humans set health |
| Forget plan-close metrics | Self-report LOC/PRs on close |

---

## Layout

```
Board/
  _system/           # THIS CORE (portable)
  config.yml         # instance
  INSTANCE.md        # instance agent overlay
  Agents/            # profiles + Plans/ + Dashboard.md
  Home.base          # kanban (Flow, Triage, Agent work)
  Tasks/             # content
  Projects/          # content
  Sprint.md          # instance state
```
