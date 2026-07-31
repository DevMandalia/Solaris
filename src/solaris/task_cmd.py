"""Create / move / edit Board tasks safely (agent execution ledger).

Usage:
  BOARD_ROOT=/path/to/instance python3 Board/_system/tools/board_task.py create --title "..." --project "Eng"
  python3 board_task.py move path-or-slug --lane "in progress now"
  python3 board_task.py list --lane "in progress now" --phase board-pm-v1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


from solaris.core import (  # noqa: E402
    ALL_LANES,
    BACKLOG_LANE,
    TRIAGE_LANE,
    TODAY,
    active_sprint,
    apply_lane,
    folder_for_project,
    infer_lane,
    iter_task_files,
    load_config,
    parse_frontmatter,
    render_frontmatter,
    slugify,
    unquote,
    write_task,
    yaml_scalar,
)


def _resolve_task(cfg, key: str) -> Path:
    key = key.strip()
    p = Path(key)
    if p.is_file():
        return p.resolve()
    cand = cfg.root / key
    if cand.is_file():
        return cand.resolve()
    # slug match
    matches = []
    for path in iter_task_files(cfg):
        if path.stem == key or path.name == key or key in path.stem:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"Task not found: {key}")
    raise SystemExit(
        "Ambiguous task id, matching:\n" + "\n".join(str(m) for m in matches[:20])
    )


def cmd_create(args: argparse.Namespace) -> int:
    cfg = load_config()
    project = args.project
    if project not in {p["name"] for p in cfg.projects}:
        # allow unknown in repo mode if folder exists / create
        if not any(p["folder"] == project for p in cfg.projects):
            print(f"warning: project {project!r} not in config; creating folder anyway", file=sys.stderr)

    source = args.source or "agent"
    lane = args.lane
    # Hard rules
    if source == "roadmap-sync" and lane == TRIAGE_LANE:
        lane = BACKLOG_LANE
    if source == "agent" and lane == TRIAGE_LANE:
        lane = args.lane if args.lane != TRIAGE_LANE else "doing this week"
        if args.lane == TRIAGE_LANE:
            lane = "doing this week"

    folder = folder_for_project(cfg, project)
    dest_dir = cfg.tasks_dir / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in dest_dir.glob("*.md")}
    slug = args.slug or slugify(args.title, existing)
    path = dest_dir / f"{slug}.md"
    if path.exists() and not args.force:
        raise SystemExit(f"Already exists: {path}")

    domain = cfg.project_domain.get(project, args.domain or "general")
    tag = cfg.project_filter_tag.get(project, project)
    week = active_sprint(cfg)

    fm: dict[str, str] = {
        "type": "task",
        "title": yaml_scalar(args.title),
        "project": yaml_scalar(project),
        "domain": domain,
        "lane": yaml_scalar(lane),
        "priority": args.priority or "P2",
        "kanban_order": str(args.order if args.order is not None else 500),
        "sprint": '""',
        "status": '""',
        "carry": "false",
        "phase": yaml_scalar(args.phase or ""),
        "blocked_reason": '""',
        "source": source,
        "created": TODAY,
        "updated": TODAY,
        "due": "",
    }
    if args.initiative_id:
        fm["initiative_id"] = args.initiative_id
    if args.roadmap_id:
        fm["roadmap_id"] = args.roadmap_id

    apply_lane(fm, lane, week)
    fm["_tags_list"] = [tag, source] if source not in (tag,) else [tag]

    if args.build:
        body = f"""
# {args.title}

## Context

{args.description or ""}

## Acceptance Criteria

{args.ac or "- [ ] Done when the change works and is verified"}

## Implementation Plan


## Subtasks

- [ ]

## Final Summary


## Log
"""
    else:
        body = f"""
# {args.title}

## Context

{args.description or ""}

## Subtasks

- [ ]

## Next steps


## Log
"""

    write_task(path, fm, body)
    rel = path.relative_to(cfg.root)
    print(rel)
    return 0


def cmd_move(args: argparse.Namespace) -> int:
    cfg = load_config()
    path = _resolve_task(cfg, args.task)
    lane = args.lane
    if lane not in ALL_LANES:
        raise SystemExit(f"Invalid lane {lane!r}. Choose from: {sorted(ALL_LANES)}")

    text = path.read_text(encoding="utf-8")
    fm, tags, body = parse_frontmatter(text)
    source = unquote(fm.get("source", ""))
    if source == "roadmap-sync" and lane == TRIAGE_LANE:
        print("roadmap-sync tasks cannot move to triage", file=sys.stderr)
        return 1
    if source == "agent" and lane == TRIAGE_LANE:
        print("agent execution tasks skip triage", file=sys.stderr)
        return 1

    week = active_sprint(cfg)
    apply_lane(fm, lane, week)
    if args.blocked_reason:
        fm["blocked_reason"] = yaml_scalar(args.blocked_reason)
    elif lane != "blocked":
        fm["blocked_reason"] = '""'
    fm["_tags_list"] = tags
    path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")
    print(f"{path.relative_to(cfg.root)} -> {lane}")
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    cfg = load_config()
    path = _resolve_task(cfg, args.task)
    text = path.read_text(encoding="utf-8")
    fm, tags, body = parse_frontmatter(text)

    if args.title:
        fm["title"] = yaml_scalar(args.title)
    if args.priority:
        fm["priority"] = args.priority
    if args.phase is not None:
        fm["phase"] = yaml_scalar(args.phase)
    if args.initiative_id is not None:
        fm["initiative_id"] = args.initiative_id
    fm["updated"] = TODAY
    fm["_tags_list"] = tags

    if args.append_log:
        stamp = TODAY
        if "## Log" in body:
            body = body.replace("## Log", f"## Log\n\n- {stamp}: {args.append_log}", 1)
        else:
            body = body.rstrip() + f"\n\n## Log\n\n- {stamp}: {args.append_log}\n"

    if args.plan is not None:
        if "## Implementation Plan" in body:
            body = re.sub(
                r"(## Implementation Plan\n)(.*?)(?=\n## |\Z)",
                r"\1\n" + args.plan.rstrip() + "\n\n",
                body,
                count=1,
                flags=re.S,
            )
        else:
            body = body.rstrip() + f"\n\n## Implementation Plan\n\n{args.plan.rstrip()}\n"

    if args.final_summary is not None:
        if "## Final Summary" in body:
            body = re.sub(
                r"(## Final Summary\n)(.*?)(?=\n## |\Z)",
                r"\1\n" + args.final_summary.rstrip() + "\n\n",
                body,
                count=1,
                flags=re.S,
            )
        else:
            body = body.rstrip() + f"\n\n## Final Summary\n\n{args.final_summary.rstrip()}\n"

    path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")
    print(path.relative_to(cfg.root))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = load_config()
    rows = []
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, _tags, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        lane = infer_lane(fm)
        phase = unquote(fm.get("phase", ""))
        project = unquote(fm.get("project", ""))
        source = unquote(fm.get("source", ""))
        if args.lane and lane != args.lane:
            continue
        if args.phase and phase != args.phase:
            continue
        if args.project and project != args.project:
            continue
        if args.source and source != args.source:
            continue
        title = unquote(fm.get("title", path.stem))
        rows.append((lane, project, phase, title, str(path.relative_to(cfg.root))))
    for lane, project, phase, title, rel in rows:
        print(f"{lane:18} {project:18} {phase:16} {title}  ({rel})")
    print(f"# {len(rows)} tasks", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Board task CLI for agents and scripts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Create a task file")
    c.add_argument("--title", required=True)
    c.add_argument("--project", required=True)
    c.add_argument("--lane", default="doing this week")
    c.add_argument("--source", default="agent")
    c.add_argument("--priority", default="P2")
    c.add_argument("--phase", default="")
    c.add_argument("--initiative-id", default="")
    c.add_argument("--roadmap-id", default="")
    c.add_argument("--domain", default="")
    c.add_argument("--description", default="")
    c.add_argument("--ac", default="")
    c.add_argument("--slug", default="")
    c.add_argument("--order", type=int, default=None)
    c.add_argument("--build", action="store_true", help="Use build-task body sections")
    c.add_argument("--force", action="store_true")
    c.set_defaults(func=cmd_create)

    m = sub.add_parser("move", help="Change lane")
    m.add_argument("task")
    m.add_argument("--lane", required=True)
    m.add_argument("--blocked-reason", default="")
    m.set_defaults(func=cmd_move)

    e = sub.add_parser("edit", help="Edit metadata / plan / log")
    e.add_argument("task")
    e.add_argument("--title")
    e.add_argument("--priority")
    e.add_argument("--phase")
    e.add_argument("--initiative-id")
    e.add_argument("--append-log")
    e.add_argument("--plan")
    e.add_argument("--final-summary")
    e.set_defaults(func=cmd_edit)

    l = sub.add_parser("list", help="List tasks")
    l.add_argument("--lane")
    l.add_argument("--phase")
    l.add_argument("--project")
    l.add_argument("--source")
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
