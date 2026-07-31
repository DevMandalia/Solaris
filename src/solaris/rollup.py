"""Roll task lane counts into initiative progress_* frontmatter keys only.

Never writes health or markdown body.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


from solaris.core import (  # noqa: E402
    TODAY,
    infer_lane,
    iter_task_files,
    load_config,
    parse_frontmatter,
    render_frontmatter,
    unquote,
)


def _initiative_indexes(cfg) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not cfg.wiki_dir or not cfg.wiki_dir.is_dir():
        return found
    for path in cfg.wiki_dir.rglob("index.md"):
        if "Initiatives" not in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        fm, _, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "initiative":
            continue
        iid = unquote(fm.get("initiative_id", ""))
        if iid:
            found[iid] = path
    return found


def run(*, dry_run: bool, force: bool) -> int:
    cfg = load_config()
    if not cfg.initiative_rollup_enabled and not force:
        print("initiative_rollup disabled in Board/config.yml (use --force to run once)")
        return 2

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"done": 0, "open": 0, "blocked": 0}
    )
    for path in iter_task_files(cfg):
        text = path.read_text(encoding="utf-8")
        fm, _, _ = parse_frontmatter(text)
        if unquote(fm.get("type", "")) != "task":
            continue
        iid = unquote(fm.get("initiative_id", ""))
        if not iid or iid == "program":
            continue
        lane = infer_lane(fm)
        if lane == "done":
            counts[iid]["done"] += 1
        elif lane == "archived":
            continue
        elif lane == "blocked":
            counts[iid]["blocked"] += 1
            counts[iid]["open"] += 1
        else:
            counts[iid]["open"] += 1

    indexes = _initiative_indexes(cfg)
    gen_dir = cfg.system_dir / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        iid: dict(c) for iid, c in sorted(counts.items())
    }
    print(json.dumps(snapshot, indent=2))

    if dry_run:
        return 0

    (gen_dir / "initiative-progress.json").write_text(
        json.dumps({"updated": TODAY, "initiatives": snapshot}, indent=2) + "\n",
        encoding="utf-8",
    )

    # Markdown snippet for Dashboard embed
    lines = [
        f"<!-- board-generated: initiative progress {TODAY} -->",
        "",
        "| Initiative | Done | Open | Blocked | Hub |",
        "|------------|-----:|-----:|--------:|-----|",
    ]
    for iid, c in sorted(snapshot.items()):
        hub = indexes.get(iid)
        link = f"[[{hub.relative_to(cfg.root)}|{iid}]]" if hub else iid
        lines.append(
            f"| {link} | {c['done']} | {c['open']} | {c['blocked']} | {iid} |"
        )
    if not snapshot:
        lines.append("| _(none)_ | 0 | 0 | 0 | |")
    (gen_dir / "initiative-progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_mode = cfg.rollup.get("write_mode", "frontmatter")
    updated = 0
    if write_mode == "frontmatter":
        for iid, c in counts.items():
            path = indexes.get(iid)
            if not path:
                continue
            text = path.read_text(encoding="utf-8")
            fm, tags, body = parse_frontmatter(text)
            before = (
                unquote(fm.get("progress_done", "")),
                unquote(fm.get("progress_open", "")),
                unquote(fm.get("progress_blocked", "")),
            )
            fm["progress_done"] = str(c["done"])
            fm["progress_open"] = str(c["open"])
            fm["progress_blocked"] = str(c["blocked"])
            # do not touch health / health_updated / body
            after = (
                fm["progress_done"],
                fm["progress_open"],
                fm["progress_blocked"],
            )
            if before == after:
                continue
            fm["_tags_list"] = tags
            path.write_text(f"---\n{render_frontmatter(fm)}\n---{body}", encoding="utf-8")
            updated += 1

    print(f"wrote generated snapshot; updated {updated} initiative frontmatter files")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    return run(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
