# Board core — safety rails

Guards that keep automation from corrupting an instance. Enforced in tools + conventions.

## Feature flags (`Board/config.yml`)

| Flag | Default intent | Risk if forced on early |
|------|----------------|-------------------------|
| `features.triage` | Intake lane available | Low |
| `features.sprint_rollover` | **Off** until `active_sprint` is correct | Mass `carry: true` + wrong week |
| `features.initiative_rollup` | Progress counts only | Noisy commits if wiki busy |

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

After plan approval: create tickets and move lanes automatically. Do not block on per-ticket human review. Prefer `board_task.py` over hand-edited YAML.
