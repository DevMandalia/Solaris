"""Export a markdown kanban snapshot (repo mode / PR status)."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path


from solaris.core import (  # noqa: E402
    ALL_LANES,
    active_sprint,
    infer_lane,
    iter_task_files,
    load_config,
    parse_frontmatter,
    unquote,
)

LANE_ORDER = [
    "triage",
    "backlog",
    "doing this week",
    "in progress now",
    "blocked",
    "done",
    "archived",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--include-done", action="store_true")
    ap.add_argument("--include-archived", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    by_lane: dict[str, list[str]] = defaultdict(list)
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, _, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        lane = infer_lane(fm)
        if lane == "done" and not args.include_done:
            continue
        if lane == "archived" and not args.include_archived:
            continue
        title = unquote(fm.get("title", path.stem))
        project = unquote(fm.get("project", ""))
        phase = unquote(fm.get("phase", ""))
        extra = f" `{phase}`" if phase else ""
        by_lane[lane].append(f"- [{project}] {title}{extra}")

    week = active_sprint(cfg)
    lines = [
        f"# Board export",
        "",
        f"Sprint: `{week}` · root: `{cfg.root}`",
        "",
    ]
    for lane in LANE_ORDER:
        if lane not in ALL_LANES:
            continue
        if lane == "done" and not args.include_done:
            continue
        if lane == "archived" and not args.include_archived:
            continue
        items = by_lane.get(lane) or []
        lines.append(f"## {lane} ({len(items)})")
        lines.append("")
        if items:
            lines.extend(items)
        else:
            lines.append("_empty_")
        lines.append("")

    text = "\n".join(lines)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
