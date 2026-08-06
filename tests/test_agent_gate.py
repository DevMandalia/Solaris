"""Tests for solaris.agent_gate (v1 / v1.5 / v2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from solaris.agent_gate import (
    GatePaths,
    bind_session,
    clear_session,
    compute_status,
    decide_mutation,
    is_bootstrap_write_path,
    is_noise_path,
    load_gate_config,
    load_session,
    mark_rules_read,
    reset_session_start,
)


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GatePaths:
    root = tmp_path / "vault"
    (root / "Board" / "Agents").mkdir(parents=True)
    (root / "Board" / "Tasks" / "Eng").mkdir(parents=True)
    (root / "Wiki" / "Eng" / "Plans").mkdir(parents=True)
    (root / ".cursor").mkdir(parents=True)
    (root / ".obsidian").mkdir(parents=True)

    (root / "Board" / "config.yml").write_text(
        """
board_root: .
board_dir: Board
tasks_dir: Board/Tasks
projects_dir: Wiki
sprint_file: Board/Sprints/index.md
wiki_dir: Wiki
agents_dir: Board/Agents
agent_dashboard: Board/Agents/Agents Dashboard.md
schema_version: 2
projects:
  - folder: Eng
    name: Eng
    filter_tag: Eng
    domain: eng
folder_aliases: {}
features:
  agent_registry: true
rollover: {}
intake: {}
rollup: {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "Board" / "Sprints").mkdir(parents=True, exist_ok=True)
    (root / "Board" / "Sprints" / "index.md").write_text(
        "---\nactive_sprint: 2026-W31\ntype: meta\ntitle: Weekly sprints\n---\n# Weekly sprints\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BOARD_ROOT", str(root))
    return GatePaths.from_root(root)


def _register(paths: GatePaths, agent_id: str = "cursor-dragonstone") -> None:
    (paths.root / "Board" / "Agents" / f"{agent_id}.md").write_text(
        f"---\ntype: agent\nagent_id: {agent_id}\ntitle: Test\nstatus: active\n"
        "plans_completed: 0\ntasks_completed: 0\nlines_added: 0\nlines_removed: 0\nprs: 0\n---\n",
        encoding="utf-8",
    )


def _open_plan(paths: GatePaths, plan_id: str = "p1", agent_id: str = "cursor-dragonstone") -> Path:
    p = paths.root / "Wiki" / "Eng" / "Plans" / f"{plan_id}.md"
    p.write_text(
        f"---\ntype: agent_plan\nplan_id: {plan_id}\nagent_id: {agent_id}\n"
        f"title: Plan\nproject: Eng\nstatus: open\n---\n# Plan\n",
        encoding="utf-8",
    )
    return p


def _task(paths: GatePaths, plan_id: str = "p1", agent_id: str = "cursor-dragonstone") -> Path:
    p = paths.root / "Board" / "Tasks" / "Eng" / "t1.md"
    p.write_text(
        f"---\ntype: task\ntitle: T\nproject: Eng\ndomain: eng\nlane: doing this week\n"
        f"source: agent\nagent_id: {agent_id}\nplan_id: {plan_id}\n---\n# T\n",
        encoding="utf-8",
    )
    return p


def test_noise_and_bootstrap_paths(vault: GatePaths):
    assert is_noise_path(vault, str(vault.root / ".obsidian" / "workspace.json"))
    assert is_bootstrap_write_path(vault, str(vault.root / "Board" / "Agents" / "x.md"))
    assert is_bootstrap_write_path(vault, str(vault.root / "Wiki" / "Eng" / "Plans" / "p.md"))
    assert not is_bootstrap_write_path(vault, str(vault.root / "Board" / "_system" / "README.md"))


def test_not_ready_denies_system_write(vault: GatePaths):
    d = decide_mutation(
        vault,
        tool_name="Write",
        file_paths=[str(vault.root / "Board" / "_system" / "README.md")],
    )
    assert d["permission"] == "deny"


def test_bootstrap_allowed_when_not_ready(vault: GatePaths):
    d = decide_mutation(
        vault,
        tool_name="Write",
        file_paths=[str(vault.root / "Board" / "Agents" / "cursor-dragonstone.md")],
    )
    assert d["permission"] == "allow"


def test_ready_with_session_bind(vault: GatePaths):
    _register(vault)
    _open_plan(vault)
    _task(vault)
    mark_rules_read(vault, "cursor-dragonstone", ["Board/_system/AGENT-CONTEXT.md"])
    status = compute_status(vault, load_gate_config(vault))
    assert status.session_bound
    assert status.ready
    d = decide_mutation(
        vault,
        tool_name="Write",
        file_paths=[str(vault.root / "Board" / "_system" / "README.md")],
    )
    assert d["permission"] == "allow"


def test_dry_run_allows_with_message(vault: GatePaths, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOARD_GATE_DRY_RUN", "1")
    d = decide_mutation(
        vault,
        tool_name="Write",
        file_paths=[str(vault.root / "Board" / "_system" / "README.md")],
    )
    assert d["permission"] == "allow"
    assert "DRY-RUN" in d.get("agent_message", "")


def test_session_start_clears_bind(vault: GatePaths):
    _register(vault)
    _open_plan(vault)
    _task(vault)
    mark_rules_read(vault, "cursor-dragonstone")
    bind_session(vault, agent_id="cursor-dragonstone", plan_id="p1", plan_path="Wiki/Eng/Plans/p1.md")
    assert compute_status(vault).ready
    reset_session_start(vault, "cursor-dragonstone")
    st = compute_status(vault)
    assert not st.rules_read
    assert not st.session_bound
    assert not st.ready


def test_clear_session_unbinds(vault: GatePaths):
    bind_session(vault, agent_id="cursor-dragonstone", plan_id="p1")
    clear_session(vault)
    assert load_session(vault) == {}


def test_tagalong_blocks_code_until_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    vault = tmp_path / "Vault"
    app = tmp_path / "App"
    (vault / "Board" / "Agents").mkdir(parents=True)
    (vault / "Board" / "Tasks" / "Eng").mkdir(parents=True)
    (vault / "Wiki" / "Eng" / "Plans").mkdir(parents=True)
    (vault / ".cursor").mkdir(parents=True)
    (app / ".cursor").mkdir(parents=True)
    (vault / "Board" / "config.yml").write_text(
        """
board_dir: Board
tasks_dir: Board/Tasks
wiki_dir: Wiki
agents_dir: Board/Agents
agent_dashboard: Board/Agents/Agents Dashboard.md
schema_version: 2
projects:
  - folder: Eng
    name: Eng
    filter_tag: Eng
    domain: eng
features:
  agent_registry: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (vault / "Board" / "Sprints").mkdir(parents=True, exist_ok=True)
    (vault / "Board" / "Sprints" / "index.md").write_text(
        "---\nactive_sprint: 2026-W31\n---\n",
        encoding="utf-8",
    )
    (app / "solaris.toml").write_text(
        f'board_root = "{vault}"\nrepo_id = "app"\n',
        encoding="utf-8",
    )
    paths = GatePaths.from_root(app)
    assert paths.workspace == app.resolve()
    assert paths.board_root == vault.resolve()
    assert paths.state.parent == app.resolve() / ".cursor"

    code_file = app / "src" / "main.py"
    code_file.parent.mkdir(parents=True)
    d = decide_mutation(paths, tool_name="Write", file_paths=[str(code_file)])
    assert d["permission"] == "deny"

    d2 = decide_mutation(
        paths,
        tool_name="Write",
        file_paths=[str(vault / "Board" / "Agents" / "cursor-dragonstone.md")],
    )
    assert d2["permission"] == "allow"

    _register(paths)
    _open_plan(paths)
    _task(paths)
    mark_rules_read(paths, "cursor-dragonstone", ["Board/_system/AGENT-CONTEXT.md"])
    assert compute_status(paths).ready
    d3 = decide_mutation(paths, tool_name="Write", file_paths=[str(code_file)])
    assert d3["permission"] == "allow"


def test_require_prd_default_off(vault: GatePaths):
    gcfg = load_gate_config(vault)
    assert gcfg.require_prd is False
