#!/usr/bin/env python3
"""Cursor hook adapter for solaris.agent_gate / <board_dir>/_system/lib/agent_gate.py

Always invoke via: python3 .cursor/hooks/agent-board-gate.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HOOK_DIR.parent.parent


def _find_lib(root: Path) -> Path | None:
    for name in (root.name, "Board"):
        lib = root / name / "_system" / "lib"
        if (lib / "agent_gate.py").is_file() or lib.is_dir():
            return lib
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        lib = child / "_system" / "lib"
        if lib.is_dir():
            return lib
    return None


try:
    from solaris.agent_gate import (  # type: ignore  # noqa: E402
        GatePaths,
        compute_status,
        decide_mutation,
        is_rules_path,
        load_gate_config,
        mark_rules_read,
        reset_session_start,
    )
except ImportError:
    LIB = _find_lib(PROJECT_ROOT) or (PROJECT_ROOT / "Board" / "_system" / "lib")
    sys.path.insert(0, str(LIB))
    from agent_gate import (  # noqa: E402
        GatePaths,
        compute_status,
        decide_mutation,
        is_rules_path,
        load_gate_config,
        mark_rules_read,
        reset_session_start,
    )


def _emit(payload: dict) -> int:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    return 0


def _deny(msg: str) -> int:
    return _emit({"permission": "deny", "agent_message": msg})


def _tool_name(data: dict) -> str:
    return (
        data.get("tool_name")
        or data.get("toolName")
        or data.get("tool")
        or (data.get("tool_input") or {}).get("tool_name")
        or ""
    )


def _tool_input(data: dict) -> dict:
    ti = data.get("tool_input") or data.get("toolInput") or data.get("input") or {}
    return ti if isinstance(ti, dict) else {}


def _extract_paths(data: dict) -> list[str]:
    ti = _tool_input(data)
    paths: list[str] = []
    for key in ("path", "file_path", "filePath", "target_notebook", "notebook_path"):
        val = ti.get(key) or data.get(key)
        if isinstance(val, str) and val:
            paths.append(val)
    if isinstance(ti.get("paths"), list):
        paths.extend(str(p) for p in ti["paths"] if p)
    return paths


def _shell_command(data: dict) -> str:
    ti = _tool_input(data)
    return str(ti.get("command") or data.get("command") or "")


def handle_session_start(_data: dict) -> int:
    paths = GatePaths.from_root(PROJECT_ROOT)
    gcfg = load_gate_config(paths)
    status = reset_session_start(paths, gcfg.agent_id)
    ctx = (
        f"Board agent gate v2 for `{status.agent_id}` "
        f"(dry_run={status.dry_run}, session_bind={gcfg.require_session_bind}).\n"
        f"Ready: {status.ready}. Missing: {', '.join(status.missing) or 'none'}.\n"
        "Read AGENT-CONTEXT → register → plan-open → session-bind → create tasks.\n"
        "`solaris agent gate-status`"
    )
    return _emit(
        {
            "env": {
                "BOARD_AGENT_ID": status.agent_id,
                "BOARD_ROOT": str(PROJECT_ROOT),
            },
            "additional_context": ctx,
        }
    )


def handle_session_end(_data: dict) -> int:
    paths = GatePaths.from_root(PROJECT_ROOT)
    from datetime import datetime, timezone

    try:
        from solaris.agent_gate import clear_session, load_state, save_state
    except ImportError:
        from agent_gate import clear_session, load_state, save_state

    gcfg = load_gate_config(paths)
    clear_session(paths)
    state = load_state(paths)
    state.pop("rules_read_at", None)
    state["session_ended_at"] = datetime.now(timezone.utc).isoformat()
    save_state(paths, state, gcfg.agent_id)
    return _emit({})


def handle_post_tool_use(data: dict) -> int:
    paths = GatePaths.from_root(PROJECT_ROOT)
    gcfg = load_gate_config(paths)
    name = _tool_name(data)
    file_paths = _extract_paths(data)
    if name in ("Read", "TabRead", "read_file"):
        hit = [p for p in file_paths if is_rules_path(p)]
        if hit:
            mark_rules_read(paths, gcfg.agent_id, hit)
    if name in ("Shell", "Bash"):
        cmd = _shell_command(data)
        if any(
            s in cmd
            for s in (
                "AGENT-CONTEXT",
                "agent-board-loop.mdc",
                "Agents/Dashboard",
                "Agents Dashboard",
            )
        ):
            mark_rules_read(paths, gcfg.agent_id, ["shell:" + cmd[:120]])
    return _emit({})


def handle_pre_tool_use(data: dict) -> int:
    paths = GatePaths.from_root(PROJECT_ROOT)
    name = _tool_name(data)
    file_paths = _extract_paths(data)
    if name in ("Read", "TabRead", "read_file"):
        gcfg = load_gate_config(paths)
        hit = [p for p in file_paths if is_rules_path(p)]
        if hit:
            mark_rules_read(paths, gcfg.agent_id, hit)
        return _emit({"permission": "allow"})

    decision = decide_mutation(
        paths,
        tool_name=name,
        file_paths=file_paths,
        shell_cmd=_shell_command(data),
    )
    return _emit(decision)


def handle_before_shell(data: dict) -> int:
    paths = GatePaths.from_root(PROJECT_ROOT)
    decision = decide_mutation(
        paths,
        tool_name="Shell",
        file_paths=[],
        shell_cmd=_shell_command(data),
    )
    return _emit(decision)


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return _deny("BOARD AGENT GATE: invalid hook payload")

    event = (
        data.get("hook_event_name")
        or data.get("event")
        or data.get("hookEvent")
        or os.environ.get("CURSOR_HOOK_EVENT", "")
    )
    if len(sys.argv) > 1 and not event:
        event = sys.argv[1]

    if event in ("sessionStart", "session_start"):
        return handle_session_start(data)
    if event in ("sessionEnd", "session_end"):
        return handle_session_end(data)
    if event in ("postToolUse", "post_tool_use"):
        return handle_post_tool_use(data)
    if event in ("preToolUse", "pre_tool_use"):
        return handle_pre_tool_use(data)
    if event in ("beforeShellExecution", "before_shell_execution"):
        return handle_before_shell(data)

    return _emit({})


if __name__ == "__main__":
    raise SystemExit(main())
