"""Board agent gate — shared logic for Cursor hooks and CLI.

v1: block until rules read + registered + open plan + ≥1 task
v1.5: bind session to a specific plan_id
v2: dry-run, path noise allowlist, testable API
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_AGENT_ID = "cursor-dragonstone"

# Legacy fixed suffixes; prefer rules_path_suffixes(board_dir) at runtime.
RULES_PATH_SUFFIXES = (
    "Board/_system/AGENT-CONTEXT.md",
    "Board/Agents/AGENT-CONTEXT.md",
    "Board/Agents/Agent-Context.md",
    "Board/Agents/INSTANCE.md",
    "Board/AGENT-CONTEXT.md",
    ".cursor/rules/agent-board-loop.mdc",
    "Board/Agents/Agents Dashboard.md",
    "Board/Agents/Dashboard.md",
    "Board/Agents Dashboard.md",
)


def rules_path_suffixes(board_dir: str = "Board") -> tuple[str, ...]:
    bd = board_dir.strip().strip("/") or "Board"
    return (
        f"{bd}/_system/AGENT-CONTEXT.md",
        f"{bd}/Agents/AGENT-CONTEXT.md",
        f"{bd}/Agents/Agent-Context.md",
        f"{bd}/Agents/INSTANCE.md",
        f"{bd}/AGENT-CONTEXT.md",
        ".cursor/rules/agent-board-loop.mdc",
        f"{bd}/Agents/Agents Dashboard.md",
        f"{bd}/Agents/Dashboard.md",
        f"{bd}/Agents Dashboard.md",
    )


def resolve_board_dir_for_root(root: Path) -> str:
    try:
        from solaris.core import find_config_path, resolve_board_dir, _parse_yaml  # type: ignore

        cfg_path = find_config_path(root)
        if cfg_path is not None:
            raw = _parse_yaml(cfg_path.read_text(encoding="utf-8"))
            return resolve_board_dir(root, raw, cfg_path)
    except Exception:
        pass
    for name in (root.name, "Board"):
        if (root / name / "config.yml").is_file():
            return name
    return "Board"

MUTATING_TOOLS = frozenset(
    {
        "Write",
        "StrReplace",
        "EditNotebook",
        "Delete",
        "DeleteFile",
        "ApplyPatch",
    }
)

# Obsidian / editor churn — never block (agents rarely own these, but tools may touch them)
NOISE_PATH_PREFIXES = (
    ".obsidian/workspace.json",
    ".obsidian/workspace-mobile.json",
    ".obsidian/backlink.json",
    ".obsidian/page-preview.json",
    ".obsidian/graph.json",
    ".trash/",
)

NOISE_PATH_SUFFIXES = (
    ".DS_Store",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(path: str | Path) -> str:
    return str(path).replace("\\", "/")


@dataclass
class GatePaths:
    root: Path
    state: Path
    session: Path
    config: Path

    @classmethod
    def from_root(cls, root: Path) -> "GatePaths":
        cursor = root / ".cursor"
        return cls(
            root=root.resolve(),
            state=cursor / "agent-gate-state.json",
            session=cursor / "agent-session.json",
            config=cursor / "agent-gate-config.json",
        )


@dataclass
class GateConfig:
    agent_id: str = DEFAULT_AGENT_ID
    dry_run: bool = False
    # When True, require session.plan_id to match an open plan (v1.5)
    require_session_bind: bool = True
    # Auto-bind when exactly one open plan exists for the agent
    auto_bind_single_plan: bool = True


@dataclass
class GateStatus:
    ready: bool
    agent_id: str
    rules_read: bool
    rules_read_at: str | None
    registered: bool
    open_plans: list[dict[str, str]] = field(default_factory=list)
    task_count: int = 0
    task_paths: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    session_plan_id: str | None = None
    session_bound: bool = False
    dry_run: bool = False


def load_gate_config(paths: GatePaths, agent_id: str | None = None) -> GateConfig:
    cfg = GateConfig(agent_id=agent_id or os.environ.get("BOARD_AGENT_ID", DEFAULT_AGENT_ID))
    env_dry = os.environ.get("BOARD_GATE_DRY_RUN", "").strip().lower()
    if env_dry in ("1", "true", "yes", "on"):
        cfg.dry_run = True
    if paths.config.is_file():
        try:
            raw = json.loads(paths.config.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if isinstance(raw, dict):
            if "dry_run" in raw:
                cfg.dry_run = bool(raw["dry_run"])
            if "require_session_bind" in raw:
                cfg.require_session_bind = bool(raw["require_session_bind"])
            if "auto_bind_single_plan" in raw:
                cfg.auto_bind_single_plan = bool(raw["auto_bind_single_plan"])
            if raw.get("agent_id"):
                cfg.agent_id = str(raw["agent_id"])
    return cfg


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["updated_at"] = _now()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_state(paths: GatePaths) -> dict[str, Any]:
    return _read_json(paths.state)


def save_state(paths: GatePaths, state: dict[str, Any], agent_id: str) -> None:
    state = dict(state)
    state["agent_id"] = agent_id
    _write_json(paths.state, state)


def load_session(paths: GatePaths) -> dict[str, Any]:
    return _read_json(paths.session)


def bind_session(
    paths: GatePaths,
    *,
    agent_id: str,
    plan_id: str,
    plan_path: str = "",
) -> dict[str, Any]:
    session = {
        "agent_id": agent_id,
        "plan_id": plan_id,
        "plan_path": plan_path,
        "bound_at": _now(),
    }
    _write_json(paths.session, session)
    return session


def clear_session(paths: GatePaths) -> None:
    if paths.session.is_file():
        paths.session.unlink()


def mark_rules_read(paths: GatePaths, agent_id: str, rule_paths: list[str] | None = None) -> None:
    state = load_state(paths)
    state["rules_read_at"] = _now()
    read = list(state.get("rules_paths_read") or [])
    for p in rule_paths or []:
        if p not in read:
            read.append(p)
    state["rules_paths_read"] = read[-20:]
    save_state(paths, state, agent_id)


def is_rules_path(path: str, board_dir: str | None = None) -> bool:
    n = _norm(path)
    suffixes = rules_path_suffixes(board_dir) if board_dir else RULES_PATH_SUFFIXES
    # Also accept any board_dir variant from common markers
    markers = (
        "/_system/AGENT-CONTEXT.md",
        "/Agents/AGENT-CONTEXT.md",
        "/Agents/Agent-Context.md",
        "/Agents/INSTANCE.md",
        "agent-board-loop.mdc",
        "/Agents/Agents Dashboard.md",
        "/Agents/Dashboard.md",
        "Agents Dashboard.md",
    )
    if any(m in n for m in markers):
        return True
    return any(n.endswith(s) or s in n for s in suffixes)


def rel_to_root(paths: GatePaths, path: str | Path) -> str | None:
    try:
        p = Path(path).expanduser().resolve()
        return _norm(p.relative_to(paths.root))
    except Exception:
        return None


def is_noise_path(paths: GatePaths, path: str) -> bool:
    rel = rel_to_root(paths, path)
    n = _norm(path)
    if any(n.endswith(suf) or n.endswith("/" + suf) for suf in NOISE_PATH_SUFFIXES):
        return True
    if rel is None:
        return False
    return any(rel == pref or rel.startswith(pref) for pref in NOISE_PATH_PREFIXES)


def is_bootstrap_write_path(paths: GatePaths, path: str) -> bool:
    rel = rel_to_root(paths, path)
    if rel is None:
        return False
    if rel in (
        ".cursor/agent-gate-state.json",
        ".cursor/agent-session.json",
        ".cursor/agent-gate-config.json",
        ".cursor/hooks.json",
    ):
        return True
    if rel.startswith(".cursor/hooks/") and rel.endswith(".py"):
        return True
    bd = resolve_board_dir_for_root(paths.root)
    if rel.startswith(f"{bd}/Agents/") and rel.endswith(".md"):
        return True
    if "/Plans/" in rel and rel.endswith(".md"):
        return True
    if rel.startswith(f"{bd}/Tasks/") and rel.endswith(".md"):
        return True
    if rel in (
        f"{bd}/Agents/Agents Dashboard.md",
        f"{bd}/Agents/Dashboard.md",
        f"{bd}/Agents Dashboard.md",
    ):
        return True
    # Legacy Board/ bootstrap during migration
    if rel.startswith("Board/Agents/") and rel.endswith(".md"):
        return True
    if rel.startswith("Board/Tasks/") and rel.endswith(".md"):
        return True
    if rel == "Board/Agents Dashboard.md":
        return True
    return False


def _find_system_lib(root: Path) -> Path | None:
    bd = resolve_board_dir_for_root(root)
    for name in (bd, "Board", root.name):
        lib = root / name / "_system" / "lib"
        if lib.is_dir():
            return lib
    return None


def _board_imports(root: Path):
    try:
        from solaris.core import (  # type: ignore
            iter_agent_plan_files,
            iter_task_files,
            load_config,
            parse_frontmatter,
            unquote,
        )
        return iter_agent_plan_files, iter_task_files, load_config, parse_frontmatter, unquote
    except ImportError:
        pass
    lib = _find_system_lib(root) or (root / "Board" / "_system" / "lib")
    import sys

    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    from board_core import (  # noqa: WPS433
        iter_agent_plan_files,
        iter_task_files,
        load_config,
        parse_frontmatter,
        unquote,
    )

    return iter_agent_plan_files, iter_task_files, load_config, parse_frontmatter, unquote


def compute_status(paths: GatePaths, gcfg: GateConfig | None = None) -> GateStatus:
    gcfg = gcfg or load_gate_config(paths)
    os.environ.setdefault("BOARD_ROOT", str(paths.root))
    iter_agent_plan_files, iter_task_files, load_config, parse_frontmatter, unquote = _board_imports(
        paths.root
    )
    cfg = load_config(paths.root)
    state = load_state(paths)
    session = load_session(paths)
    rules_read = bool(state.get("rules_read_at"))
    registered = (cfg.agents_dir / f"{gcfg.agent_id}.md").is_file()

    open_plans: list[dict[str, str]] = []
    for path in iter_agent_plan_files(cfg):
        fm, _t, _b = parse_frontmatter(path.read_text(encoding="utf-8"))
        if unquote(fm.get("agent_id", "")) != gcfg.agent_id:
            continue
        if unquote(fm.get("status", "")) != "open":
            continue
        if "/Agents/Plans/" in _norm(path):
            continue
        open_plans.append(
            {
                "plan_id": unquote(fm.get("plan_id", path.stem)),
                "path": _norm(path.relative_to(cfg.root)),
                "title": unquote(fm.get("title", "")),
            }
        )

    session_plan_id = str(session.get("plan_id") or "") or None
    if (
        gcfg.auto_bind_single_plan
        and not session_plan_id
        and len(open_plans) == 1
        and rules_read
        and registered
    ):
        only = open_plans[0]
        bind_session(
            paths,
            agent_id=gcfg.agent_id,
            plan_id=only["plan_id"],
            plan_path=only["path"],
        )
        session_plan_id = only["plan_id"]
        session = load_session(paths)

    # If bound plan is no longer open, clear bind
    open_ids = {p["plan_id"] for p in open_plans}
    if session_plan_id and session_plan_id not in open_ids:
        clear_session(paths)
        session_plan_id = None
        session = {}

    plan_ids = open_ids
    if gcfg.require_session_bind and session_plan_id:
        plan_ids = {session_plan_id}

    task_count = 0
    task_paths: list[str] = []
    if plan_ids:
        for path in iter_task_files(cfg):
            fm, _t, _b = parse_frontmatter(path.read_text(encoding="utf-8"))
            if unquote(fm.get("type", "")) != "task":
                continue
            if unquote(fm.get("agent_id", "")) != gcfg.agent_id:
                continue
            if unquote(fm.get("plan_id", "")) not in plan_ids:
                continue
            task_count += 1
            task_paths.append(_norm(path.relative_to(cfg.root)))

    session_bound = bool(session_plan_id) and session_plan_id in open_ids
    missing: list[str] = []
    bd = getattr(cfg, "board_dir", None) or resolve_board_dir_for_root(paths.root)
    if not rules_read:
        missing.append(
            f"Read {bd}/_system/AGENT-CONTEXT.md (or .cursor/rules/agent-board-loop.mdc)"
        )
    if not registered:
        missing.append(
            f"Register: solaris agent register --id {gcfg.agent_id} --name ... --model ... --owner ..."
        )
    if not open_plans:
        missing.append(
            f"Open a plan: board_agent.py plan-open --agent {gcfg.agent_id} --title ... --project ..."
        )
    if gcfg.require_session_bind and open_plans and not session_bound:
        missing.append(
            "Bind session to a plan: board_agent.py session-bind --plan-id <id> "
            "(auto if exactly one open plan)"
        )
    if task_count < 1:
        missing.append(
            f"Create todos: board_task.py create --agent {gcfg.agent_id} --plan-id <id> ..."
        )

    ready = (
        rules_read
        and registered
        and bool(open_plans)
        and task_count >= 1
        and (session_bound or not gcfg.require_session_bind)
    )

    return GateStatus(
        ready=ready,
        agent_id=gcfg.agent_id,
        rules_read=rules_read,
        rules_read_at=state.get("rules_read_at"),
        registered=registered,
        open_plans=open_plans,
        task_count=task_count,
        task_paths=task_paths[:10],
        missing=missing,
        session_plan_id=session_plan_id,
        session_bound=session_bound,
        dry_run=gcfg.dry_run,
    )


def blocking_message(status: GateStatus) -> str:
    lines = [
        f"BOARD AGENT GATE: blocked until {status.agent_id} completes session setup.",
        "Missing:",
    ]
    for m in status.missing:
        lines.append(f"  - {m}")
    lines.extend(
        [
            "",
            "Session start:",
            "  1) Read <board_dir>/_system/AGENT-CONTEXT.md",
            f"  2) Ensure registered: <board_dir>/Agents/{status.agent_id}.md",
            f"  3) solaris agent plan-open --agent {status.agent_id} --title ... --project ...",
            "  4) solaris agent session-bind --plan-id <id>  (auto if only one open plan)",
            f"  5) solaris task create ... --agent {status.agent_id} --plan-id <id>",
            "  6) Retry your edit",
            "",
            "Check: solaris agent gate-status",
            "Dry-run: BOARD_GATE_DRY_RUN=1 or .cursor/agent-gate-config.json {\"dry_run\": true}",
        ]
    )
    return "\n".join(lines)


def shell_allowed_while_blocked(cmd: str) -> bool:
    c = cmd.strip()
    if not c:
        return True
    if re.search(r"board_agent\.py|board_task\.py|solaris\s+agent|solaris\s+task", c):
        return True
    if re.match(
        r"^(ls|pwd|echo|whoami|date|rg|grep|find|cat|head|tail|less|wc|"
        r"git\s+(status|diff|log|show|branch)|python3\s+-c\s+['\"]print)",
        c,
    ):
        return True
    if "/_system/tools/board_agent.py" in c or "/_system/tools/board_task.py" in c:
        return True
    if "/_system/lib/agent_gate.py" in c:
        return True
    return False


def decide_mutation(
    paths: GatePaths,
    *,
    tool_name: str,
    file_paths: list[str],
    shell_cmd: str = "",
    gcfg: GateConfig | None = None,
) -> dict[str, Any]:
    """Return a hook-style decision: {permission, agent_message?, user_message?}."""
    gcfg = gcfg or load_gate_config(paths)
    name = tool_name or ""

    # Always-allow noise
    if file_paths and all(is_noise_path(paths, p) for p in file_paths):
        return {"permission": "allow"}

    if name in ("Read", "TabRead", "read_file", "Grep", "Glob", "SemanticSearch"):
        return {"permission": "allow"}

    status = compute_status(paths, gcfg)

    if name in ("Shell", "Bash"):
        if status.ready:
            return {"permission": "allow"}
        if shell_allowed_while_blocked(shell_cmd):
            return {"permission": "allow"}
        return _deny_or_dry(status, gcfg)

    if name in MUTATING_TOOLS or name.startswith("Edit"):
        if not file_paths:
            return _deny_or_dry(status, gcfg)
        if all(is_bootstrap_write_path(paths, p) or is_noise_path(paths, p) for p in file_paths):
            return {"permission": "allow"}
        if status.ready:
            # v1.5: task files for other agents/plans still allowed if bootstrap;
            # non-bootstrap OK when session bound + ready
            return {"permission": "allow"}
        return _deny_or_dry(status, gcfg)

    return {"permission": "allow"}


def _deny_or_dry(status: GateStatus, gcfg: GateConfig) -> dict[str, Any]:
    msg = blocking_message(status)
    if gcfg.dry_run or status.dry_run:
        return {
            "permission": "allow",
            "agent_message": f"[BOARD GATE DRY-RUN] would deny:\n{msg}",
            "user_message": "Board agent gate dry-run: edit allowed but would be blocked.",
        }
    return {"permission": "deny", "agent_message": msg}


def reset_session_start(paths: GatePaths, agent_id: str) -> GateStatus:
    """sessionStart: require re-read of rules; clear session bind."""
    state = load_state(paths)
    state.pop("rules_read_at", None)
    state["session_started_at"] = _now()
    save_state(paths, state, agent_id)
    clear_session(paths)
    return compute_status(paths, load_gate_config(paths, agent_id))
