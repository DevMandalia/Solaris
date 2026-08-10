"""Scaffold a Solaris board instance in any directory or git repo.

Board folder defaults to the host directory basename (e.g. init in ~/acme → acme/acme/).
Override with --board-dir. Legacy name `Board` is still supported.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from importlib import resources
from pathlib import Path


def _share_dir() -> Path:
    """Locate packaged data/ (templates, base, docs seeds)."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "data",
        Path(str(resources.files("solaris"))) / "data",
    ]
    for c in candidates:
        try:
            c = Path(c)
        except TypeError:
            continue
        if (c / "templates").is_dir():
            return c
    raise FileNotFoundError("Solaris data/ assets not found — reinstall the package")


def install_cursor_gate(repo_root: Path, *, force: bool = False) -> Path:
    """Install Cursor agent-board-gate hooks into a linked code repo (tag-along).

    Vendors ``.cursor/lib/`` so system ``python3`` can import the gate without
    ``pip install solaris`` (avoids fail-closed deadlock on import errors).
    """
    share = _share_dir()
    cursor_src = share / "cursor"
    if not cursor_src.is_dir():
        raise FileNotFoundError("Packaged cursor gate assets missing")
    repo_root = repo_root.expanduser().resolve()
    cursor_dst = repo_root / ".cursor"
    cursor_dst.mkdir(parents=True, exist_ok=True)
    hooks_src = cursor_src / "hooks.json"
    if hooks_src.is_file() and (force or not (cursor_dst / "hooks.json").exists()):
        shutil.copy2(hooks_src, cursor_dst / "hooks.json")
    cfg_src = cursor_src / "agent-gate-config.json"
    if cfg_src.is_file() and (force or not (cursor_dst / "agent-gate-config.json").exists()):
        shutil.copy2(cfg_src, cursor_dst / "agent-gate-config.json")
    hooks_py_src = cursor_src / "hooks"
    if hooks_py_src.is_dir():
        (cursor_dst / "hooks").mkdir(exist_ok=True)
        for py in hooks_py_src.glob("*.py"):
            if force or not (cursor_dst / "hooks" / py.name).exists():
                shutil.copy2(py, cursor_dst / "hooks" / py.name)

    # Vendor gate modules for system python3 (PEP 668 / no global pip)
    lib_dst = cursor_dst / "lib"
    lib_dst.mkdir(exist_ok=True)
    try:
        pkg = Path(str(resources.files("solaris")))
        for name, dest_name in (
            ("agent_gate.py", "agent_gate.py"),
            ("core.py", "board_core.py"),
        ):
            src = pkg / name
            dest = lib_dst / dest_name
            if src.is_file() and (force or not dest.exists()):
                shutil.copy2(src, dest)
        sol = lib_dst / "solaris"
        sol.mkdir(exist_ok=True)
        init_f = sol / "__init__.py"
        if force or not init_f.exists():
            # Stamp the version actually being vendored. A hardcoded literal
            # here silently mislabels every vendored copy after the next
            # release, so `solaris doctor` (and humans) cannot tell a stale
            # tag-along lib from a current one.
            from solaris import __version__ as _pkg_version

            init_f.write_text(f'__version__ = "{_pkg_version}"\n', encoding="utf-8")
        for name in ("agent_gate.py", "core.py"):
            src = pkg / name
            dest = sol / name
            if src.is_file() and (force or not dest.exists()):
                shutil.copy2(src, dest)
    except Exception:
        pass
    return cursor_dst


def write_solaris_toml(
    repo_root: Path,
    *,
    board_root: Path,
    repo_id: str = "",
    force: bool = False,
) -> Path:
    """Write solaris.toml pointer in a code repo."""
    repo_root = repo_root.expanduser().resolve()
    dest = repo_root / "solaris.toml"
    if dest.exists() and not force:
        raise FileExistsError(f"Exists: {dest} (pass force=True to overwrite)")
    br = str(board_root.expanduser().resolve())
    lines = [
        "# Solaris tag-along pointer — board/wiki live in board_root, not this repo",
        f'board_root = "{br}"',
    ]
    if repo_id:
        lines.append(f'repo_id = "{repo_id}"')
    lines.append("")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def install_obsidian_scaffold(root: Path, *, force: bool = False) -> Path | None:
    """Write .obsidian/ with Bases (core), Base Board plugin, and Nebula theme.

    If `.obsidian/` already exists and force is False, leave it untouched and return None.
    With force=True, merge seed files into the existing vault config.
    """
    share = _share_dir()
    src = share / "obsidian"
    if not src.is_dir():
        raise FileNotFoundError("Solaris data/obsidian/ seed missing — reinstall the package")
    dst = root / ".obsidian"
    if dst.exists() and not force:
        return None
    if dst.exists() and force:
        for path in src.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return dst
    shutil.copytree(src, dst)
    return dst


def init_board(
    root: Path,
    *,
    name: str = "Project",
    project: str | None = None,
    board_dir: str | None = None,
    force: bool = False,
    obsidian: bool = False,
) -> Path:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    project = project or name
    bd = (board_dir or root.name).strip().strip("/") or "Board"
    board = root / bd
    cfg_path = board / "config.yml"
    share = _share_dir()

    if cfg_path.exists() and not force:
        raise FileExistsError(f"Already initialized: {cfg_path}")

    board.mkdir(parents=True, exist_ok=True)
    system = board / "_system"
    if system.exists():
        if not force:
            raise FileExistsError(f"Exists: {system}")
        shutil.rmtree(system)
    system.mkdir(parents=True)

    shutil.copytree(share / "templates", system / "templates")
    shutil.copytree(share / "base", system / "base")
    (system / "generated").mkdir(exist_ok=True)
    (system / "generated" / "initiative-progress.md").write_text(
        "<!-- solaris-generated: run `solaris rollup` -->\n\n"
        "| Initiative | Done | Open | Blocked |\n"
        "|------------|-----:|-----:|--------:|\n"
        "| _(none)_ | 0 | 0 | 0 |\n",
        encoding="utf-8",
    )

    docs_src = share / "docs"
    if docs_src.is_dir():
        for name_doc in ("AGENT-CONTEXT.md", "SAFETY.md", "README.md"):
            src = docs_src / name_doc
            if src.is_file():
                shutil.copy2(src, system / name_doc)

    cursor_src = share / "cursor"
    if cursor_src.is_dir():
        cursor_dst = root / ".cursor"
        cursor_dst.mkdir(parents=True, exist_ok=True)
        hooks_src = cursor_src / "hooks.json"
        if hooks_src.is_file() and (force or not (cursor_dst / "hooks.json").exists()):
            shutil.copy2(hooks_src, cursor_dst / "hooks.json")
        cfg_src = cursor_src / "agent-gate-config.json"
        if cfg_src.is_file() and (force or not (cursor_dst / "agent-gate-config.json").exists()):
            shutil.copy2(cfg_src, cursor_dst / "agent-gate-config.json")
        hooks_py_src = cursor_src / "hooks"
        if hooks_py_src.is_dir():
            (cursor_dst / "hooks").mkdir(exist_ok=True)
            for py in hooks_py_src.glob("*.py"):
                shutil.copy2(py, cursor_dst / "hooks" / py.name)
        lib_dst = system / "lib"
        lib_dst.mkdir(exist_ok=True)
        try:
            gate_pkg = Path(str(resources.files("solaris"))) / "agent_gate.py"
            if gate_pkg.is_file():
                shutil.copy2(gate_pkg, lib_dst / "agent_gate.py")
            core_pkg = Path(str(resources.files("solaris"))) / "core.py"
            if core_pkg.is_file():
                shutil.copy2(core_pkg, lib_dst / "board_core.py")
        except Exception:
            pass

    week = date.today().strftime("%G-W%V")
    cfg_path.write_text(
        f"""# Solaris board instance config
board_root: .
board_dir: {bd}
tasks_dir: {bd}/Tasks
projects_dir: Wiki
sprint_file: {bd}/Sprints/index.md
wiki_dir: Wiki
agents_dir: {bd}/Agents
agent_dashboard: {bd}/Agents/Agents Dashboard.md
schema_version: 2

projects:
  - folder: {project}
    name: {project}
    filter_tag: {project}
    domain: eng

folder_aliases: {{}}
legacy_filter_tags: []

features:
  triage: true
  sprint_rollover: true
  initiative_rollup: false
  agent_registry: true

rollover:
  max_week_gap: 1
  mark_carry_lanes:
    - doing this week
    - in progress now
    - blocked
  sprints_dir: {bd}/Sprints
  archive_home: true
  patch_home_base: true

intake:
  default_lane: triage

rollup:
  write_mode: frontmatter
""",
        encoding="utf-8",
    )

    (board / "Tasks" / project).mkdir(parents=True, exist_ok=True)

    wiki_hub = root / "Wiki" / project
    wiki_hub.mkdir(parents=True, exist_ok=True)
    (wiki_hub / "index.md").write_text(
        f"""---
type: project
title: {project}
domain: eng
status: active
---

# {project}

Project hub. Tasks: `{bd}/Tasks/{project}/`.

- [[../../{bd}/Dashboard|Command Center]]
- [[../../{bd}/Home.base|{bd} board]]
- [[AGENTS|Agent instructions]] (optional)

view: [[../../{bd}/Home.base#{project}|{project} tasks]]
""",
        encoding="utf-8",
    )

    core_base = share / "base" / "Home.core.base"
    if not core_base.is_file():
        core_base = share / "base" / "Board.core.base"
    if core_base.is_file():
        shutil.copy2(core_base, board / "Home.base")


    (board / "Dashboard.md").write_text(
        f"""---
cssclasses:
  - board-dashboard
---

# Command Center — {name}

> [!tip] Flow board
> **Triage** — human intake (accept → backlog). Agent plan tickets skip triage.
> **Backlog** — top = highest priority. Drag into **doing this week** for the sprint.
> **Agents** — [[{bd}/Agents/Agents Dashboard|Agents Dashboard]] (register → plan → tasks).

## Triage

![[{bd}/Home.base#Triage]]

## Flow

![[{bd}/Home.base#Flow]]

## Agent work

[[{bd}/Agents/Agents Dashboard|Agents Dashboard]]

![[{bd}/Home.base#Agent work]]

## Epics

| Epic | Wiki hub |
|------|----------|
| {project} | [[Wiki/{project}/index|{project}]] |

New tasks: `solaris task create` or **+** on Home.base.

---

[[{bd}/Agents/Agents Dashboard|Agents]] · [[{bd}/Agents/AGENT-CONTEXT|Agent entry]] · [[Welcome]]

---

## WTFAQs

How **you** use the board. Agents: [[{bd}/Agents/AGENT-CONTEXT]] → [[{bd}/_system/AGENT-CONTEXT]] + [[{bd}/Agents/INSTANCE|INSTANCE]].

**Lanes:** triage → backlog → doing this week → in progress now → blocked → done / archived

### Daily rhythm?

1. Open this Dashboard.
2. Clear **Triage** if anything is waiting.
3. Work from **in progress now** (~1–3 cards).
4. Pull next from **doing this week** when you start something.
5. Ship → **done**. Cancel → **archived** (not done).
6. Stuck → **blocked** + one-line reason.

### What do I do with Triage?

| Action | Do this |
|--------|---------|
| Accept | Drag to **backlog** (or **doing this week**). |
| Reject | Drag to **archived**. |
| Needs thought | Leave in triage; clear by weekly review. |

### How does capture work?

| How | What happens |
|-----|----------------|
| Review → board | Card in **triage** |
| Manual / CLI / **+** on board | Card in **backlog** (`source: board`) |
| Agent executes an approved plan | Agent files tickets and moves them |

Human scratch: [[To Do]] → promote into Triage. Board tasks are the SoT — not `To Do.md`.

### How do I watch agents?

1. [[{bd}/Agents/Agents Dashboard|Agents Dashboard]] — profiles, plans, LOC/PRs.
2. [[{bd}/Home.base#Agent work|Agent work]] — live lanes.
3. Open plans under `Wiki/<Project>/…/Plans/`.

### Quick links?

| | |
|--|--|
| All views | [[{bd}/Home.base]] |
| Agents Dashboard | [[{bd}/Agents/Agents Dashboard]] |
| Agent entry | [[{bd}/Agents/AGENT-CONTEXT]] |
| Instance routing | [[{bd}/Agents/INSTANCE]] |
| Portable schema | [[{bd}/_system/AGENT-CONTEXT]] |
""",
        encoding="utf-8",
    )

    agents = board / "Agents"
    agents.mkdir(parents=True, exist_ok=True)

    (agents / "Agents Dashboard.md").write_text(
        f"""---
type: meta
title: Agents Dashboard
audience: humans+agents
cssclasses:
  - agent-dashboard
updated: {date.today().isoformat()}
---

# Agents Dashboard

<!-- agent-metrics:start -->
<div class="agent-roster"></div>
<!-- agent-metrics:end -->

> [!warning] Hard rules
> 1. **Register** (or confirm your profile) before touching any code.
> 2. **Open a plan** after user approval — write it under the **project / initiative wiki**, file tasks with `agent_id` + `plan_id`.
> 3. Execute on [[{bd}/Home.base#Agent work|Home.base → Agent work]]; mark tasks **done** as you finish.
> 4. **Close the plan** with self-reported LOC/PR metrics.

### Session start

```bash
export BOARD_ROOT={root}
solaris agent list
solaris agent list --plans --open
solaris agent gate-status
```

CLI: `solaris agent …`

## Open plans

_No open plans._

## Agent work

Live lanes for `source: agent` cards — same view as [[{bd}/Home.base#Agent work|Home.base → Agent work]].

![[{bd}/Home.base#Agent work]]

## Boards

- [[{bd}/Home.base#By agent|By agent]] — open agent work grouped by `agent_id`
- [[{bd}/Home.base#Flow|Flow]] — full execution ledger
- [[{bd}/Dashboard|Command Center]]
- Agent profiles: `{bd}/Agents/<agent_id>.md`

## Register

```bash
solaris agent register \\
  --id my-agent --name "My Agent" --model "model-id" --owner "Your Name"
```
""",
        encoding="utf-8",
    )

    (agents / "AGENT-CONTEXT.md").write_text(
        f"""---
type: meta
title: Agent entry
audience: agents
scope: entrypoint (core + instance)
---

# Agent entry — {name}

1. **Portable core:** [[{bd}/_system/AGENT-CONTEXT]]
2. **This instance:** [[{bd}/Agents/INSTANCE|INSTANCE]]
3. **Command center:** [[{bd}/Dashboard]] · [[{bd}/Home.base]] · [[{bd}/Sprint]]
4. **Agents Dashboard:** [[{bd}/Agents/Agents Dashboard|Dashboard]]

Config: [[{bd}/config.yml]] · Profiles: `{bd}/Agents/<agent_id>.md`

**Before any code:** register on the Agents Dashboard, open a plan, file tasks with `--agent` / `--plan-id`.
""",
        encoding="utf-8",
    )

    (agents / "INSTANCE.md").write_text(
        f"""---
type: meta
title: Instance overlay — {name}
audience: agents
---

# Instance overlay — {name}

**Read first:** [[{bd}/_system/AGENT-CONTEXT]] (portable schema).  
**Root:** `{root}` · `BOARD_ROOT={root}` · `board_dir: {bd}`

## Projects

| Task folder | `project` | Filter tag |
|-------------|-----------|------------|
| {project} | {project} | {project} |

Config SSOT: [[{bd}/config.yml]]

## Surfaces

| Need | Go to |
|------|--------|
| Human how-to | [[{bd}/Dashboard#WTFAQs|WTFAQs]] |
| Command center | [[{bd}/Dashboard]] |
| Agents Dashboard | [[{bd}/Agents/Agents Dashboard]] |
| Project hub | `Wiki/{project}/index.md` |
| Welcome | [[Welcome]] |

## Agent gate

Cursor agents are gated by `.cursor/hooks.json`. Before mutating, run:

```bash
export BOARD_ROOT={root}
solaris agent gate-status
```
""",
        encoding="utf-8",
    )

    
    # Current week sprint folder (plan / goals / retro stubs)
    try:
        from solaris.core import ensure_week_folder, write_sprint_pointer, update_sprints_index, patch_home_base_sprint_filter
        from datetime import date as _date
        _week = _date.today().strftime("%G-W%V")
        # load_config needs config on disk — already written
        from solaris.core import load_config
        _cfg = load_config(root)
        ensure_week_folder(_cfg, _week, write_home_snapshot=False)
        write_sprint_pointer(_cfg, _week)
        update_sprints_index(_cfg, current_week=_week)
        patch_home_base_sprint_filter(board / "Home.base", _week)
    except Exception:
        pass

    (root / "Notes").mkdir(exist_ok=True)
    (root / "Notes" / ".gitkeep").write_text("", encoding="utf-8")

    (root / "To Do.md").write_text(
        """# To Do

Human capture scratch. Promote items into Triage / board tasks — board tasks are the SoT.
""",
        encoding="utf-8",
    )

    (root / "Welcome.md").write_text(
        f"""---
type: meta
title: Welcome
---

# {name}

Markdown-native project board (Solaris) in this repo.

| Need | Go |
|------|-----|
| Command center + how-to | [[{bd}/Dashboard]] · [[{bd}/Dashboard#WTFAQs\\|WTFAQs]] |
| Kanban | [[{bd}/Home.base]] |
| Agents | [[{bd}/Agents/Agents Dashboard\\|Dashboard]] · [[{bd}/Agents/AGENT-CONTEXT\\|entry]] |
| Capture | [[To Do]] → Triage |
| Project wiki | [[Wiki/{project}/index\\|{project}]] |

## Layout

```
{bd}/Tasks/           execution SoT
{bd}/Agents/          entry, INSTANCE, Dashboard, profiles
{bd}/Dashboard.md     command center + WTFAQs
{bd}/_system/         engine (hide in Obsidian file explorer)
Wiki/<Project>/       project homes
Notes/                braindump
To Do.md              human capture scratch
```

CLI: `export BOARD_ROOT={root}` then `solaris task …` / `solaris agent …`
""",
        encoding="utf-8",
    )
    # Fix over-escaped wiki pipes in Welcome
    welcome = root / "Welcome.md"
    welcome.write_text(welcome.read_text(encoding="utf-8").replace("\\|", "|"), encoding="utf-8")

    (root / "AGENTS.md").write_text(
        f"""# Agent instructions — {name}

This repo uses **Solaris** (markdown project board).

1. Read `{bd}/_system/AGENT-CONTEXT.md`
2. Read `{bd}/Agents/INSTANCE.md`
3. Prefer CLI: `solaris task create|move|edit|list` (set `BOARD_ROOT` to this repo root)

Do not put `source: agent` tasks in triage. After a plan is approved, create tickets and move lanes automatically.
""",
        encoding="utf-8",
    )

    if obsidian:
        install_obsidian_scaffold(root, force=force)

    return root


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Initialize a Solaris board")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--name", default="Project")
    ap.add_argument("--project", default=None)
    ap.add_argument(
        "--board-dir",
        default=None,
        help="Board folder name (default: basename of --root)",
    )
    ap.add_argument(
        "--obsidian",
        action="store_true",
        help="Scaffold .obsidian/ with Bases, Base Board plugin, and Nebula theme",
    )
    ap.add_argument(
        "--link",
        action="store_true",
        help="Install Cursor gate hooks into a code repo (tag-along); does not scaffold a board",
    )
    ap.add_argument(
        "--board-root",
        type=Path,
        default=None,
        help="With --link: write solaris.toml pointing at this vault",
    )
    ap.add_argument(
        "--repo-id",
        default="",
        help="With --link: repo_id for solaris.toml / linked_repos",
    )
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.link:
        root = args.root.expanduser().resolve()
        try:
            cursor = install_cursor_gate(root, force=args.force)
        except FileNotFoundError as e:
            print(e, file=__import__("sys").stderr)
            return 1
        print(f"Installed Cursor gate into {cursor}")
        if args.board_root:
            try:
                toml = write_solaris_toml(
                    root,
                    board_root=args.board_root,
                    repo_id=args.repo_id,
                    force=args.force,
                )
                print(f"Wrote {toml}")
            except FileExistsError as e:
                print(e, file=__import__("sys").stderr)
                return 1
        else:
            print("Tip: pass --board-root ~/Vault --repo-id myrepo to write solaris.toml")
        print("Next: solaris doctor  (from the code repo)")
        return 0

    try:
        root = init_board(
            args.root,
            name=args.name,
            project=args.project,
            board_dir=args.board_dir,
            force=args.force,
            obsidian=args.obsidian,
        )
    except FileExistsError as e:
        print(e, file=__import__("sys").stderr)
        return 1
    project = args.project or args.name
    root = root.resolve()
    bd = (args.board_dir or root.name).strip().strip("/") or "Board"
    print(f"Initialized Solaris board at {root}")
    print(f"  board_dir: {bd}")
    print(f"  project: {project}")
    if args.obsidian:
        print("  obsidian: .obsidian/ (Bases + Base Board + Nebula)")
    print("Next:")
    print(f"  export BOARD_ROOT={root}")
    if args.obsidian:
        print("  Install Obsidian.app (see README), then: Open folder as vault → this directory")
    print(
        f'  solaris task create --title "First task" --project "{project}" --build'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
