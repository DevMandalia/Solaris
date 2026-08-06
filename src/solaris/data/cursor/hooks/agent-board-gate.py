#!/usr/bin/env python3
"""Cursor hook adapter for solaris.agent_gate (tag-along safe).

Always invoke via: python3 .cursor/hooks/agent-board-gate.py

Resilience rules (binding):
- Never crash the process on import/runtime infrastructure errors.
- On infra failure: emit permission=allow + agent_message warning (fail OPEN).
- Intentional gate denies still return permission=deny (fail closed for policy).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HOOK_DIR.parent.parent


def _emit(payload: dict) -> int:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    return 0


def _allow(msg: str = "") -> int:
    payload: dict = {"permission": "allow"}
    if msg:
        payload["agent_message"] = msg
    return _emit(payload)


def _deny(msg: str) -> int:
    return _emit({"permission": "deny", "agent_message": msg})


def _bootstrap_imports() -> None:
    candidates = [
        PROJECT_ROOT / ".cursor" / "lib",
        Path.home() / "Solaris" / "src",
        Path("/Users/DevaangMandalia/Solaris/src"),
    ]
    for c in candidates:
        if c.is_dir() and str(c) not in sys.path:
            sys.path.insert(0, str(c))


def _load_gate():
    """Import gate API or raise ImportError."""
    _bootstrap_imports()
    try:
        from solaris.agent_gate import (  # type: ignore
            GatePaths,
            decide_mutation,
            is_rules_path,
            load_gate_config,
            mark_rules_read,
            reset_session_start,
        )
        return GatePaths, decide_mutation, is_rules_path, load_gate_config, mark_rules_read, reset_session_start
    except ImportError:
        lib = PROJECT_ROOT / ".cursor" / "lib"
        if str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        from agent_gate import (  # type: ignore
            GatePaths,
            decide_mutation,
            is_rules_path,
            load_gate_config,
            mark_rules_read,
            reset_session_start,
        )
        return GatePaths, decide_mutation, is_rules_path, load_gate_config, mark_rules_read, reset_session_start


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


def handle_session_start(_data: dict, api) -> int:
    GatePaths, _dm, _irp, load_gate_config, _mrr, reset_session_start = api
    paths = GatePaths.from_root(PROJECT_ROOT)
    gcfg = load_gate_config(paths)
    status = reset_session_start(paths, gcfg.agent_id)
    tag = ""
    if paths.workspace != paths.board_root:
        tag = f" tag-along board={paths.board_root}"
    ctx = (
        f"Board agent gate v2.1 for `{status.agent_id}` "
        f"(dry_run={status.dry_run}, session_bind={gcfg.require_session_bind},"
        f" require_prd={gcfg.require_prd}).{tag}\n"
        f"Ready: {status.ready}. Missing: {', '.join(status.missing) or 'none'}.\n"
        "Read AGENT-CONTEXT → register → plan-open → session-bind → create tasks.\n"
        "`solaris doctor` · `solaris agent gate-status`"
    )
    return _emit(
        {
            "env": {
                "BOARD_AGENT_ID": status.agent_id,
                "BOARD_ROOT": str(paths.board_root),
            },
            "additional_context": ctx,
        }
    )


def handle_session_end(_data: dict, api) -> int:
    GatePaths, *_rest = api
    from datetime import datetime, timezone

    try:
        from solaris.agent_gate import clear_session, load_state, save_state
    except ImportError:
        from agent_gate import clear_session, load_state, save_state

    paths = GatePaths.from_root(PROJECT_ROOT)
    load_gate_config = api[3]
    gcfg = load_gate_config(paths)
    clear_session(paths)
    state = load_state(paths)
    state.pop("rules_read_at", None)
    state["session_ended_at"] = datetime.now(timezone.utc).isoformat()
    save_state(paths, state, gcfg.agent_id)
    return _emit({})


def handle_post_tool_use(data: dict, api) -> int:
    GatePaths, _dm, is_rules_path, load_gate_config, mark_rules_read, _rss = api
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


def handle_pre_tool_use(data: dict, api) -> int:
    GatePaths, decide_mutation, is_rules_path, load_gate_config, mark_rules_read, _rss = api
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


def handle_before_shell(data: dict, api) -> int:
    GatePaths, decide_mutation, *_rest = api
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
        # Bad payload — fail open so the agent is not deadlocked
        return _allow("BOARD AGENT GATE: invalid hook payload (allowed fail-open)")

    event = (
        data.get("hook_event_name")
        or data.get("event")
        or data.get("hookEvent")
        or os.environ.get("CURSOR_HOOK_EVENT", "")
    )
    if len(sys.argv) > 1 and not event:
        event = sys.argv[1]

    try:
        api = _load_gate()
    except Exception as exc:
        return _allow(
            "BOARD AGENT GATE: import/runtime failure — fail OPEN so agents can self-heal.\n"
            f"{type(exc).__name__}: {exc}\n"
            "Fix: ensure Direction-Sky/.cursor/lib has agent_gate.py "
            "or PYTHONPATH includes Solaris/src. Then reload."
        )

    try:
        if event in ("sessionStart", "session_start"):
            return handle_session_start(data, api)
        if event in ("sessionEnd", "session_end"):
            return handle_session_end(data, api)
        if event in ("postToolUse", "post_tool_use"):
            return handle_post_tool_use(data, api)
        if event in ("preToolUse", "pre_tool_use"):
            return handle_pre_tool_use(data, api)
        if event in ("beforeShellExecution", "before_shell_execution"):
            return handle_before_shell(data, api)
        return _emit({})
    except Exception as exc:
        tb = traceback.format_exc(limit=3)
        return _allow(
            f"BOARD AGENT GATE: runtime error — fail OPEN.\n{type(exc).__name__}: {exc}\n{tb}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
