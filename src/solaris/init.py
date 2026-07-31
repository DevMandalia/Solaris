"""Scaffold a Solaris Board instance in any directory or git repo."""

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


def init_board(
    root: Path,
    *,
    name: str = "Project",
    project: str | None = None,
    force: bool = False,
) -> Path:
    root = root.expanduser().resolve()
    project = project or name
    board = root / "Board"
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

    # Copy templates + base into _system (portable core mirror)
    shutil.copytree(share / "templates", system / "templates")
    shutil.copytree(share / "base", system / "base")
    (system / "generated").mkdir(exist_ok=True)
    (system / "generated" / "initiative-progress.md").write_text(
        "<!-- solaris-generated: run `solaris-board rollup` -->\n\n"
        "| Initiative | Done | Open | Blocked |\n"
        "|------------|-----:|-----:|--------:|\n"
        "| _(none)_ | 0 | 0 | 0 |\n",
        encoding="utf-8",
    )

    # Seed agent + human docs into _system
    docs_src = share / "docs"
    if docs_src.is_dir():
        for name_doc in ("AGENT-CONTEXT.md", "SAFETY.md", "Humans.md", "README.md"):
            src = docs_src / name_doc
            if src.is_file():
                shutil.copy2(src, system / name_doc)

    week = date.today().strftime("%G-W%V")
    cfg_path.write_text(
        f"""# Solaris Board instance config
board_root: .
tasks_dir: Board/Tasks
projects_dir: Board/Projects
sprint_file: Board/Sprint.md
wiki_dir: null
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
  sprint_rollover: false
  initiative_rollup: false

rollover:
  max_week_gap: 1
  mark_carry_lanes:
    - doing this week
    - in progress now
    - blocked

intake:
  default_lane: triage

rollup:
  write_mode: frontmatter
""",
        encoding="utf-8",
    )

    (board / "Tasks" / project).mkdir(parents=True, exist_ok=True)
    (board / "Projects").mkdir(parents=True, exist_ok=True)
    (board / "Projects" / f"{project}.md").write_text(
        f"""---
type: project
title: {project}
domain: eng
status: active
tags:
  - project
---

# {project}

Project hub. Tasks: `Board/Tasks/{project}/`.

See [Humans](Humans.md) · [_system/AGENT-CONTEXT](_system/AGENT-CONTEXT.md).
""",
        encoding="utf-8",
    )

    templates = board / "Templates"
    templates.mkdir(exist_ok=True)
    for src in (system / "templates").glob("*.md"):
        dest_name = {
            "task.md": "New Task.md",
            "task-build.md": "New Task — Build.md",
            "initiative.md": "New Initiative.md",
            "project.md": "New Project.md",
        }.get(src.name, src.name)
        shutil.copy2(src, templates / dest_name)

    shutil.copy2(share / "base" / "Board.core.base", board / "Board.base")

    (board / "Sprint.md").write_text(
        f"""---
active_sprint: {week}
---

# Active sprint

ISO week `{week}`. Edit when starting a new week.
""",
        encoding="utf-8",
    )

    (board / "Dashboard.md").write_text(
        f"""# Command Center — {name}

## Triage

See `Board.base` → Triage.

## Flow

Open `Board.base` → Flow.

**Humans:** [[Board/Humans]] · **Agents:** [[Board/_system/AGENT-CONTEXT]]
""",
        encoding="utf-8",
    )

    if (system / "Humans.md").is_file():
        shutil.copy2(system / "Humans.md", board / "Humans.md")
    else:
        (board / "Humans.md").write_text(
            "# Humans\n\nSee documentation in the Solaris repo: docs/humans.md\n",
            encoding="utf-8",
        )

    (board / "INSTANCE.md").write_text(
        f"""---
type: meta
title: Solaris instance — {name}
---

# Solaris instance — {name}

1. Read [[Board/_system/AGENT-CONTEXT]]
2. Read [[Board/Humans]]
3. Projects are listed in `Board/config.yml` (this instance: **{project}**)
""",
        encoding="utf-8",
    )

    (board / "AGENT-CONTEXT.md").write_text(
        """---
type: meta
title: Solaris agent entry
---

# Solaris agent entry

1. [[Board/_system/AGENT-CONTEXT]]
2. [[Board/INSTANCE]]
""",
        encoding="utf-8",
    )

    (root / "AGENTS.md").write_text(
        f"""# Agent instructions — {name}

This repo uses **Solaris** (markdown project board).

1. Read `Board/_system/AGENT-CONTEXT.md`
2. Read `Board/INSTANCE.md`
3. Prefer CLI: `solaris-board task create|move|edit|list` (set `BOARD_ROOT` to this repo root)

Do not put `source: agent` tasks in triage. After a plan is approved, create tickets and move lanes automatically.
""",
        encoding="utf-8",
    )

    return root


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Initialize a Solaris board")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--name", default="Project")
    ap.add_argument("--project", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    try:
        root = init_board(
            args.root, name=args.name, project=args.project, force=args.force
        )
    except FileExistsError as e:
        print(e, file=__import__("sys").stderr)
        return 1
    project = args.project or args.name
    print(f"Initialized Solaris board at {root}")
    print(f"  project: {project}")
    print("Next:")
    print(f"  export BOARD_ROOT={root}")
    print(
        f'  solaris-board task create --title "First task" --project "{project}" --build'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
