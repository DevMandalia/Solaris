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
Safety rails: SAFETY.md (gap guard, source→lane rules, rollup write scope, feature flags).

---

## TL;DR

1. **Hierarchy:** Project → optional Initiative → Task (flat files under `Board/Tasks/<folder>/`).
2. **Lanes:** `triage` → `backlog` → `doing this week` → `in progress now` → `blocked` → `done` / `archived`.
3. **`done` = shipped.** **`archived` = withdrawn** (not shipped).
4. **Mutate tasks via CLI** — `board_task.py` create/move/edit — do not hand-edit YAML frontmatter.
5. **Agent execution is automatic** after the user accepts a plan: create tickets, move lanes, no per-ticket human gate.
6. **`source: agent`** tickets never use `triage`. **`source: roadmap-sync`** never uses `triage`.

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

**Human gate (once):** user approves the plan / says execute.  
**After that:** do not wait for per-ticket review.

1. Create one task per concrete work unit (`board_task.py create --source agent --build` for implementation).
2. Prefer `lane: doing this week` when executing now; put the first unit in `in progress now` immediately.
3. While working: `move --lane "in progress now"` → implement → Log / Final Summary → `move --lane done`.
4. New work discovered → create another agent task and continue (do not silently expand scope).
5. True external wait → `blocked` + reason; continue other ready tickets when possible.

History lives in task files + git. The board is an execution ledger, not an approval inbox.

**Skip tickets** for trivial one-shot asks. **Always file tickets** for multi-step plan execution.

---

## CLI

```bash
export BOARD_ROOT=/path/to/instance   # optional if cwd/config discoverable

python3 Board/_system/tools/board_task.py create \
  --title "Extract portable core" --project "Acme" --build \
  --phase my-initiative --lane "doing this week"

python3 Board/_system/tools/board_task.py move <slug-or-path> --lane "in progress now"
python3 Board/_system/tools/board_task.py move <slug-or-path> --lane done
python3 Board/_system/tools/board_task.py list --phase my-initiative
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
| Hand-edit task YAML | `board_task.py` |
| Put `source: agent` in triage | `doing this week` / `in progress now` |
| Put roadmap-sync in triage | Always backlog (+ lane drag) |
| Wait for human on every ticket | Auto-move after plan approval |
| `lane: done` for cancelled work | `archived` |
| Write health from rollup scripts | Humans set health |

---

## Layout

```
Board/
  _system/           # THIS CORE (portable)
  config.yml         # instance
  INSTANCE.md        # instance agent overlay
  Tasks/             # content
  Projects/          # content
  Sprint.md          # instance state
```
