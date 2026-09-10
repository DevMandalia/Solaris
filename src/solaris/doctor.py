"""solaris doctor — verify tag-along board binding and gate readiness hints."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from solaris.core import (
    find_config_path,
    find_solaris_pointer,
    iter_board_markdown,
    load_config,
    load_solaris_pointer,
    resolve_board_root,
)


def _fingerprint(root: Path) -> str:
    cfg = find_config_path(root)
    seed = f"{root.resolve()}|{cfg}"
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def run_doctor(start: Path | None = None) -> int:
    start = (start or Path.cwd()).resolve()
    print(f"cwd: {start}")

    ptr_path = find_solaris_pointer(start)
    if ptr_path:
        try:
            ptr = load_solaris_pointer(ptr_path)
            print(f"pointer: {ptr_path}")
            print(f"  board_root: {ptr.board_root}")
            print(f"  repo_id: {ptr.repo_id or '(unset)'}")
        except ValueError as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 1
    else:
        print("pointer: (none — using BOARD_ROOT or local board config)")

    try:
        root = resolve_board_root(start)
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"board_root: {root}")
    print(f"fingerprint: {_fingerprint(root)}")

    try:
        cfg = load_config(root)
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print(f"board_dir: {cfg.board_dir}")
    print(f"schema_version: {cfg.schema_version}")
    print(f"projects: {len(cfg.projects)}")

    if cfg.linked_repos:
        print("linked_repos:")
        for lr in cfg.linked_repos:
            exists = lr.path.is_dir()
            mark = "ok" if exists else "MISSING"
            print(f"  - id={lr.id} path={lr.path} [{mark}]")
    else:
        print("linked_repos: (none)")

    # Gate config presence (board and/or workspace)
    board_gate = root / ".cursor" / "agent-gate-config.json"
    ws_gate = start / ".cursor" / "agent-gate-config.json"
    print(f"gate config (board): {'yes' if board_gate.is_file() else 'no'}")
    print(f"gate config (cwd): {'yes' if ws_gate.is_file() else 'no'}")

    agents = iter_board_markdown(cfg.agents_dir, recursive=False)
    skip = {
        "Agents Dashboard.md",
        "Dashboard.md",
        "INSTANCE.md",
        "AGENT-CONTEXT.md",
        "Agent-Context.md",
    }
    agent_profiles = [p for p in agents if p.name not in skip]
    print(f"agent profiles: {len(agent_profiles)}")

    if ptr_path:
        ptr = load_solaris_pointer(ptr_path)
        if ptr.repo_id and cfg.linked_repos:
            ids = {lr.id for lr in cfg.linked_repos}
            if ptr.repo_id not in ids:
                print(
                    f"WARN: repo_id={ptr.repo_id!r} not in vault linked_repos ids={sorted(ids)}",
                    file=sys.stderr,
                )
            else:
                match = next(lr for lr in cfg.linked_repos if lr.id == ptr.repo_id)
                pointer_root = ptr_path.parent.resolve()
                if pointer_root != match.path.resolve():
                    print(
                        f"WARN: pointer parent {pointer_root} != linked_repos[{ptr.repo_id}].path={match.path}",
                        file=sys.stderr,
                    )

    print("doctor: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="solaris doctor")
    ap.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Start directory (default: process cwd)",
    )
    args = ap.parse_args(argv)
    return run_doctor(args.cwd)
