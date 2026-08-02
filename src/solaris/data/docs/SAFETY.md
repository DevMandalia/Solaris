# Board core — safety rails

Guards that keep automation from corrupting an instance. Enforced in tools + conventions.

## Feature flags (`Board/config.yml`)

| Flag | Default intent | Risk if forced on early |
|------|----------------|-------------------------|
| `features.triage` | Intake lane available | Low |
| `features.sprint_rollover` | **Off** until `active_sprint` is correct | Mass `carry: true` + wrong week |
| `features.initiative_rollup` | Progress counts only | Noisy commits if wiki busy |
| `features.agent_registry` | Require `agent_id` + `plan_id` on `source: agent` creates | Agents blocked until registered |

Nightly hooks must treat exit code **2** (flag off) as success/no-op.

## Sprint gap guard

`board_sprint_rollover.py` compares stored `active_sprint` to today's ISO week.

- `delta == 0` → no-op
- `abs(delta) <= max_week_gap` (default **1**) → bump week + mark carry
- `abs(delta) > max_week_gap` → **ABORT**, no file writes (unless `--force`)

Never auto-heal a multi-week stale sprint. Fix `Board/Sprint.md` manually first.

## Source → lane hard rules

| `source` | May use `triage`? |
|----------|-------------------|
| intake adapters (e.g. sauna-review) | Yes |
| `agent` | **No** — execution ledger |
| `roadmap-sync` | **No** — stays backlog (+ lane drag) |
| `board` (manual) | Prefer backlog |

Enforced in `board_task.py` create/move.

## Agent registry

When `features.agent_registry` is on:

- `board_task.py create --source agent` requires a registered `--agent` and an open `--plan-id`.
- Plan files live under the **project/initiative wiki** (`Wiki/<Project>/Plans/` or `…/Initiatives/<id>/Plans/`), not under `Board/Agents/`.
- Plan close metrics (`lines_added` / `lines_removed` / `prs`) are **self-reported** — tools do not scrape git in v1.
- Agent rollup counters on `Board/Agents/<id>.md` are tool-owned (written by `plan-close`).
- Agents Dashboard lives at `Board/Agents Dashboard.md` (regenerated roster).

## No mass migrate

- Existing tasks are not bulk-moved into `triage`.
- Intake adapters change **new** creates only.
- `done` vs `archived` semantics unchanged.

## Rollup write scope

`board_initiative_rollup.py` may write only:

- `progress_done` / `progress_open` / `progress_blocked` on initiative frontmatter
- `Board/_system/generated/initiative-progress.{md,json}`

Must **never** write `health`, `health_updated`, or initiative markdown body (`## Status`).

## Dual SoT

Do not read/write instance `To Do.md` (or equivalent legacy ledgers). Board tasks are the execution SoT.

## Agent loop

After plan approval: create tickets and move lanes automatically. Do not block on per-ticket human review. Prefer `board_task.py` / `solaris task` over hand-edited YAML.

## Cursor agent-board-gate

Logic: `solaris.agent_gate` · Hook: `.cursor/hooks/agent-board-gate.py` (installed by `solaris init`)

### Modes

| Mode | How |
|------|-----|
| Enforce (default) | `failClosed: true` on preToolUse / beforeShellExecution |
| Dry-run | `BOARD_GATE_DRY_RUN=1` or `.cursor/agent-gate-config.json` `"dry_run": true` |
| Emergency off | Rename `.cursor/hooks.json` → `hooks.json.off.json` |

### Session bind (v1.5)

`.cursor/agent-session.json` holds `{agent_id, plan_id}`. Cleared on `sessionStart`, `sessionEnd`, and `plan-close` of the bound plan. Auto-binds when exactly one open plan exists.

Unlock requires:

1. Rules read this session (`Board/_system/AGENT-CONTEXT.md`)
2. Registered profile under `Board/Agents/`
3. Open wiki plan **and session bind** (`plan-open` auto-binds; or `session-bind --plan-id`)
4. ≥1 Board task with that `plan_id`

```bash
solaris agent gate-status
solaris agent session-bind --plan-id <id>
```

**Hermes:** no Cursor hooks — run `solaris agent gate-status` as preflight before mutating.
