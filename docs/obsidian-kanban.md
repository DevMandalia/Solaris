# Obsidian Kanban (`Home.base`) — troubleshooting

Solaris boards use Obsidian **Bases** plus the **Base Board** community plugin, which registers the Bases view type `kanban`. Classic “Kanban” plugins do **not** fix this.

## Symptom

Opening `<board_dir>/Home.base` shows:

```text
unknown view type: kanban
```

or an empty / broken board after `solaris init --obsidian`.

## Cause

1. **Restricted mode** is on (default for a newly opened vault). Community plugins under `.obsidian/plugins/` are present on disk but **do not load**.
2. **Base Board** is disabled in Community plugins.
3. Rare: Base Board loads before Bases finishes registering — mitigated by the vendored **Solaris Kanban Fix** plugin (retries / stub).

Solaris can vendor plugins and enable them in `community-plugins.json`, but **Obsidian still requires a human to turn off Restricted mode once** for that vault. There is no supported file-only bypass.

## Fix (once per vault)

1. Confirm you opened the **vault folder** (with `--vault-repo`, that is the sibling `*-vault` directory — not the code repo).
2. **Settings → Community plugins → Turn off Restricted mode**.
3. Enable **Base Board** and **Solaris Kanban Fix**.
4. Command palette → **Reload app without saving**.
5. Re-open `<board_dir>/Home.base`.

Optional: Command palette → **Solaris: Diagnose Bases kanban** (prints whether Bases / Base Board / `kanban` are registered).

## After `solaris init --obsidian`

Init prints the same checklist. Seed lives in `src/solaris/data/obsidian/` (Base Board + Solaris Kanban Fix + Nebula + Bases core enabled).

## Related

- Tag-along vaults: `solaris init --obsidian --vault-repo`
- Humans guide: [humans.md](humans.md)
