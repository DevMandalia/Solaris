# Agent instructions — Solaris (this repository)

When contributing to or using Solaris itself:

1. Read [docs/agents.md](docs/agents.md) and [docs/safety.md](docs/safety.md).
2. Prefer `solaris task` CLI for any board mutations in example/smoke boards.
3. Never commit personal task content into this repo — only fixtures under `tests/` or `examples/`.
4. Keep `src/solaris/` and `src/solaris/data/` free of instance-specific project names.

## Planes (fleet) — do not merge

| Plane | System | Role |
|---|---|---|
| Fact | DSKY Turso | Money / audit |
| Memory | Team-Memory (Railway) | Lessons, skills, prefs — **only** memory SoR |
| Work + record | This board/wiki (Dragonstone or other vault) | Kanban, PRDs, plans, tickets, agent performance |
| Code | Linked repos (`solaris.toml` → `board_root`) | Patches / PRs |

- Protocol: `~/Dragonstone/Wiki/Dragonstone Ops/Team-Memory/protocol.md`
- MCP: `team-memory` (Railway primary; Mem0 failover removed 2026-08-14)
- No A2A; correct via PR + board; DSKY Turso wins for financial facts
- **Solaris is not a memory layer.** Do not store Chat Memory under the vault. Skills SoR = Team-Memory; wiki prose SoR = `Wiki/`
- Tag-along: code repos use `solaris.toml`; run `solaris doctor` to verify binding
- Cursor hard-gates code edits until register + plan-open + session-bind + ≥1 task; PRDs are soft
