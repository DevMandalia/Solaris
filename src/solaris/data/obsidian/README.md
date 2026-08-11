# Obsidian vault seed (Solaris)

Written by `solaris init --obsidian` (and `--vault-repo`).

| Piece | Role |
|-------|------|
| **Bases** (core) | `.base` files / views |
| **Base Board** | Registers Bases view type `kanban` (drag-and-drop board) |
| **Solaris Kanban Fix** | Retries / stubs `kanban` if Base Board loses the race on first load |
| **Nebula** | Theme |

## First open (required once per vault)

Obsidian cannot turn off Restricted mode from files alone. On first open of a new vault:

1. **Settings → Community plugins → Turn off Restricted mode** (allow community plugins).
2. Confirm **Base Board** and **Solaris Kanban Fix** are enabled.
3. Command palette → **Reload app without saving**.
4. Open `<board_dir>/Home.base`.

Until Restricted mode is off, `Home.base` shows **`unknown view type: kanban`** even though plugins are vendored under `.obsidian/plugins/`.

## Fix: `unknown view type: kanban`

See the Solaris package doc **`docs/obsidian-kanban.md`** (same steps).
