# Concepts

| Term | Meaning |
|------|---------|
| **Instance** | A vault/`BOARD_ROOT` with board dir + `config.yml` and your tasks |
| **Core** | Portable engine + schema (this package / `Board/_system`) |
| **Tag-along** | Board/wiki vault separate from code git trees; code repos point at the vault via `solaris.toml` |
| **Linked repo** | Entry in vault `linked_repos` (id + path); mirrored by `repo_id` in the code repo’s `solaris.toml` |
| **Project** | Top-level work area → folder under `Board/Tasks/` |
| **Initiative** | Multi-step effort; optional hub + `health` + progress counts |
| **Task** | One Markdown file = one kanban card |
| **Lane** | Column: triage, backlog, doing this week, in progress now, blocked, done, archived |
| **Phase** | Free label linking a batch of related tasks |
| **Source** | Provenance: `board`, `agent`, `roadmap-sync`, or intake-specific |

**Planes:** Solaris owns work + project record (board, wiki, PRDs, plans, tickets, agent performance). It is **not** a Chat Memory layer — fleet memory lives in Team-Memory (see Dragonstone Team-Memory protocol). Prefer tag-along vaults over nesting the board inside an application repo when one vault serves multiple codebases.

**Scaffold tag-along:** from a code repo, `solaris init --name App --obsidian --vault-repo` creates a sibling `<basename>-vault` git repo (board + wiki + `.obsidian`), writes `linked_repos` there, and writes `solaris.toml` in the code repo. Override path with `--vault-path`; optional `--github` runs `gh repo create`. In-repo `solaris init --obsidian` (no `--vault-repo`) still scaffolds into `--root` for single-folder experiments.

Discovery: `BOARD_ROOT` env → `solaris.toml` / `.solaris/config.toml` walk-up → fail closed. Verify with `solaris doctor`.

See also [humans.md](humans.md) and [agents.md](agents.md).
