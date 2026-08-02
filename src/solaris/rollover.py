"""Safe ISO-week sprint rollover with gap guard + weekly Home archive."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from solaris.core import (
    TODAY,
    active_sprint,
    ensure_week_folder,
    infer_lane,
    iso_week_delta,
    iter_task_files,
    load_config,
    parse_frontmatter,
    patch_home_base_sprint_filter,
    render_frontmatter,
    set_active_sprint,
    sprint_folder_name,
    sprints_dir,
    unquote,
    update_sprints_index,
    write_sprint_pointer,
)

def _home_base_path(cfg) -> Path:
    return cfg.root / cfg.board_dir / "Home.base"


def _archive_enabled(cfg) -> bool:
    return cfg.rollover.get("archive_home", True) is not False


def _patch_enabled(cfg) -> bool:
    return cfg.rollover.get("patch_home_base", True) is not False


def run(*, dry_run: bool, force: bool, seed_only: bool = False) -> int:
    cfg = load_config()
    if seed_only:
        current = date.today().strftime("%G-W%V")
        print(f"seed-only: ensure week folder + Sprints/index + Home filter for {current}")
        if dry_run:
            print(f"  would create {sprints_dir(cfg) / sprint_folder_name(current)}")
            return 0
        ensure_week_folder(cfg, current, write_home_snapshot=False)
        write_sprint_pointer(cfg, current)
        set_active_sprint(cfg, current)
        write_sprint_pointer(cfg, current)
        update_sprints_index(cfg, current_week=current)
        if _patch_enabled(cfg):
            ok = patch_home_base_sprint_filter(_home_base_path(cfg), current)
            print(f"  Home.base filter patched={ok}")
        print(f"seeded {sprints_dir(cfg) / sprint_folder_name(current)}")
        return 0

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
        print("no-op: already on current week (use --seed-current to create week folder)")
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

    closed_folder = sprints_dir(cfg) / sprint_folder_name(stored)
    new_folder = sprints_dir(cfg) / sprint_folder_name(current)
    print(
        f"would archive → {closed_folder.relative_to(cfg.root)}/home.md; "
        f"mark carry on {len(to_carry)} tasks; bump sprint → {current}; "
        f"seed {new_folder.relative_to(cfg.root)}"
    )
    if dry_run:
        for p in to_carry[:30]:
            print(f"  CARRY {p.relative_to(cfg.root)}")
        if len(to_carry) > 30:
            print(f"  ... +{len(to_carry) - 30} more")
        return 0

    # 1) Archive closed week (snapshot includes Done)
    if _archive_enabled(cfg):
        ensure_week_folder(
            cfg,
            stored,
            write_home_snapshot=True,
            home_title=f"Home — {stored} (closed)",
        )
        print(f"archived {closed_folder.relative_to(cfg.root)}/home.md")

    # 2) Carry unfinished sprint work
    for path in to_carry:
        text = path.read_text(encoding="utf-8")
        fm, tags, body = parse_frontmatter(text)
        fm["carry"] = "true"
        fm["updated"] = TODAY
        fm["_tags_list"] = tags
        path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")

    # 3) Bump sprint + seed new week
    set_active_sprint(cfg, current)
    ensure_week_folder(cfg, current, write_home_snapshot=False)
    write_sprint_pointer(cfg, current)
    update_sprints_index(cfg, current_week=current, closed_week=stored)

    # 4) Patch Home.base Done filter
    if _patch_enabled(cfg):
        ok = patch_home_base_sprint_filter(_home_base_path(cfg), current)
        print(f"Home.base Done filter → {current} patched={ok}")

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
    ap.add_argument(
        "--seed-current",
        action="store_true",
        help="Create current week Sprints/ folder + index.md + Home filter (no carry)",
    )
    args = ap.parse_args()
    return run(dry_run=args.dry_run, force=args.force, seed_only=args.seed_current)


if __name__ == "__main__":
    raise SystemExit(main())
