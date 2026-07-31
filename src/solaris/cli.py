"""Solaris CLI — init, task, export, sync, rollover, rollup."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] in ("-h", "--help"):
        _print_help()
        return 0
    if argv and argv[0] in ("-V", "--version"):
        from solaris import __version__

        print(__version__)
        return 0

    # Global --cwd before subcommand
    if "--cwd" in argv:
        i = argv.index("--cwd")
        if i + 1 >= len(argv):
            print("--cwd requires a path", file=sys.stderr)
            return 2
        os.environ["BOARD_ROOT"] = str(Path(argv[i + 1]).expanduser().resolve())
        del argv[i : i + 2]

    if not argv:
        _print_help()
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd == "init":
        from solaris.init import main as init_main

        return init_main(rest)

    if cmd == "task":
        from solaris import task_cmd

        old = sys.argv
        try:
            sys.argv = ["solaris-task", *rest]
            return task_cmd.main()
        finally:
            sys.argv = old

    if cmd == "export":
        from solaris import export as export_mod

        old = sys.argv
        try:
            sys.argv = ["solaris-export", *rest]
            return export_mod.main()
        finally:
            sys.argv = old

    if cmd == "sync":
        from solaris.core import load_config
        from solaris.sync import sync_all

        n = sync_all(load_config())
        print(f"Synced {n} task file(s)")
        return 0

    if cmd == "rollover":
        from solaris.rollover import run

        ap = argparse.ArgumentParser(prog="solaris rollover")
        ap.add_argument("--dry-run", action="store_true")
        ap.add_argument("--force", action="store_true")
        args = ap.parse_args(rest)
        return run(dry_run=args.dry_run, force=args.force)

    if cmd == "rollup":
        from solaris.rollup import run

        ap = argparse.ArgumentParser(prog="solaris rollup")
        ap.add_argument("--dry-run", action="store_true")
        ap.add_argument("--force", action="store_true")
        args = ap.parse_args(rest)
        return run(dry_run=args.dry_run, force=args.force)

    print(f"Unknown command: {cmd}", file=sys.stderr)
    _print_help()
    return 2


def _print_help() -> None:
    print(
        """Solaris — markdown-native project board for humans and AI agents

Usage:
  solaris-board [--cwd DIR] <command> ...
  python -m solaris [--cwd DIR] <command> ...

Commands:
  init       Scaffold Board/ in a directory or git repo
  task       create | move | edit | list
  export     Markdown kanban snapshot
  sync       Sync lane → sprint/status fields
  rollover   Safe ISO-week sprint rollover
  rollup     Initiative progress_* counts

Examples:
  solaris-board init --name MyApp --project Eng
  export BOARD_ROOT=$PWD
  solaris-board task create --title "Ship CLI" --project Eng --build
  solaris-board task move ship-cli --lane "in progress now"
  solaris-board export --include-done
"""
    )


if __name__ == "__main__":
    raise SystemExit(main())
