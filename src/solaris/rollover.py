"""Safe ISO-week sprint rollover with gap guard.

Refuses to run when |delta| > max_week_gap (default 1) unless --force.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


from solaris.core import (  # noqa: E402
    TODAY,
    active_sprint,
    infer_lane,
    iso_week_delta,
    iter_task_files,
    load_config,
    parse_frontmatter,
    render_frontmatter,
    set_active_sprint,
    unquote,
)


def run(*, dry_run: bool, force: bool) -> int:
    cfg = load_config()
    if not cfg.sprint_rollover_enabled and not force:
        print("sprint_rollover disabled in Board/config.yml (use --force to run once)")
        return 2

    current = date.today().strftime("%G-W%V")
    stored = active_sprint(cfg)
    try:
        delta = iso_week_delta(stored, current)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    max_gap = int(cfg.rollover.get("max_week_gap", 1))
    print(f"stored={stored} current={current} delta={delta} max_week_gap={max_gap}")

    if delta == 0:
        print("no-op: already on current week")
        return 0

    if abs(delta) > max_gap and not force:
        print(
            f"ABORT: week gap {delta} exceeds max_week_gap={max_gap}. "
            f"Manually set active_sprint to {current} in {cfg.sprint_file}, "
            "then re-run with --force if you intend to mark carry.",
            file=sys.stderr,
        )
        return 1

    mark_lanes = set(
        cfg.rollover.get("mark_carry_lanes")
        or ["doing this week", "in progress now", "blocked"]
    )
    to_carry: list[Path] = []
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, tags, body = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        lane = infer_lane(fm)
        if lane not in mark_lanes:
            continue
        to_carry.append(path)

    print(f"would mark carry on {len(to_carry)} tasks; bump sprint → {current}")
    if dry_run:
        for p in to_carry[:30]:
            print(f"  CARRY {p.relative_to(cfg.root)}")
        if len(to_carry) > 30:
            print(f"  ... +{len(to_carry) - 30} more")
        return 0

    for path in to_carry:
        text = path.read_text(encoding="utf-8")
        fm, tags, body = parse_frontmatter(text)
        fm["carry"] = "true"
        fm["updated"] = TODAY
        fm["_tags_list"] = tags
        path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")

    set_active_sprint(cfg, current)
    print(f"updated {len(to_carry)} tasks; active_sprint={current}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Run even if feature flag off or week gap > max",
    )
    args = ap.parse_args()
    return run(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
