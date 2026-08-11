"""End-to-end smoke for init → create → move → export."""

from __future__ import annotations

from pathlib import Path

import pytest

from solaris.cli import main as cli_main
from solaris.core import discover_root, load_config, infer_lane, parse_frontmatter, unquote


@pytest.fixture()
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init with explicit Board/ for backward-compat tests."""
    root = tmp_path / "DemoRepo"
    root.mkdir()
    monkeypatch.setenv("BOARD_ROOT", str(root))
    assert (
        cli_main(
            [
                "init",
                "--root",
                str(root),
                "--name",
                "Demo",
                "--project",
                "Eng",
                "--board-dir",
                "Board",
            ]
        )
        == 0
    )
    assert (root / "Board" / "config.yml").is_file()
    return root


@pytest.fixture()
def acme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init with default board_dir = basename (AcmeDemo)."""
    root = tmp_path / "AcmeDemo"
    root.mkdir()
    monkeypatch.setenv("BOARD_ROOT", str(root))
    assert cli_main(["init", "--root", str(root), "--name", "Acme", "--project", "Eng"]) == 0
    assert (root / "AcmeDemo" / "config.yml").is_file()
    assert (root / "Welcome.md").is_file()
    assert (root / "Wiki" / "Eng" / "index.md").is_file()
    assert (root / "Notes").is_dir()
    assert (root / "To Do.md").is_file()
    assert not (root / "AcmeDemo" / "Templates").exists()
    assert not (root / "AcmeDemo" / "Projects").exists()
    assert not (root / "AcmeDemo" / "Humans.md").exists()
    return root


def _register_and_plan(board: Path) -> str:
    assert (
        cli_main(
            [
                "agent",
                "register",
                "--id",
                "bot",
                "--name",
                "Bot",
                "--model",
                "test",
                "--owner",
                "Tester",
            ]
        )
        == 0
    )
    assert (
        cli_main(
            [
                "agent",
                "plan-open",
                "--agent",
                "bot",
                "--title",
                "Smoke",
                "--project",
                "Eng",
                "--plan-id",
                "smoke-plan",
            ]
        )
        == 0
    )
    return "smoke-plan"


def test_init_repo_named_board_dir(acme: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(acme))
    cfg = load_config()
    assert cfg.board_dir == "AcmeDemo"
    assert cfg.tasks_dir == acme / "AcmeDemo" / "Tasks"
    assert cfg.agent_dashboard == acme / "AcmeDemo" / "Agents" / "Agents Dashboard.md"
    assert (acme / "AcmeDemo" / "Agents" / "INSTANCE.md").is_file()
    assert "Agent work" in (acme / "AcmeDemo" / "Agents" / "Agents Dashboard.md").read_text()
    assert "WTFAQs" in (acme / "AcmeDemo" / "Dashboard.md").read_text()


def test_discover_root_finds_basename_board(acme: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    found = discover_root(acme / "AcmeDemo" / "Tasks")
    assert found == acme.resolve()


def test_init_has_no_instance_leaks(board: Path) -> None:
    text = ""
    for p in (board / "Board" / "_system").rglob("*.md"):
        text += p.read_text(encoding="utf-8")
    for bad in ("Dragonstone", "Polaris", "Sauna", "Personal", "G&A"):
        assert bad not in text, bad


def test_init_installs_cursor_gate(board: Path) -> None:
    assert (board / ".cursor" / "hooks.json").is_file()
    assert (board / ".cursor" / "hooks" / "agent-board-gate.py").is_file()
    assert (board / ".cursor" / "agent-gate-config.json").is_file()


def test_init_obsidian_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "VaultDemo"
    root.mkdir()
    monkeypatch.setenv("BOARD_ROOT", str(root))
    assert (
        cli_main(
            [
                "init",
                "--root",
                str(root),
                "--name",
                "Vault",
                "--project",
                "Eng",
                "--obsidian",
            ]
        )
        == 0
    )
    assert (root / ".obsidian" / "appearance.json").is_file()
    assert "Nebula" in (root / ".obsidian" / "appearance.json").read_text()
    assert (root / ".obsidian" / "plugins" / "base-board" / "main.js").is_file()
    assert (root / ".obsidian" / "plugins" / "solaris-kanban-fix" / "main.js").is_file()
    enabled = (root / ".obsidian" / "community-plugins.json").read_text()
    assert "base-board" in enabled
    assert "solaris-kanban-fix" in enabled
    assert (root / ".obsidian" / "themes" / "Nebula" / "theme.css").is_file()
    cores = (root / ".obsidian" / "core-plugins.json").read_text()
    assert '"bases": true' in cores or '"bases":true' in cores
    welcome = (root / "Welcome.md").read_text(encoding="utf-8")
    assert "Turn off Restricted mode" in welcome
    assert "unknown view type: kanban" in welcome
    # without --obsidian, no .obsidian
    root2 = tmp_path / "CliOnly"
    root2.mkdir()
    monkeypatch.setenv("BOARD_ROOT", str(root2))
    assert cli_main(["init", "--root", str(root2), "--name", "Cli", "--project", "Eng"]) == 0
    assert not (root2 / ".obsidian").exists()


def test_task_lifecycle(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    plan_id = _register_and_plan(board)
    assert (
        cli_main(
            [
                "task",
                "create",
                "--title",
                "Ship feature",
                "--project",
                "Eng",
                "--build",
                "--lane",
                "doing this week",
                "--phase",
                "demo",
                "--agent",
                "bot",
                "--plan-id",
                plan_id,
            ]
        )
        == 0
    )
    assert cli_main(["task", "move", "ship-feature", "--lane", "in progress now"]) == 0
    assert cli_main(["task", "move", "ship-feature", "--lane", "done"]) == 0
    path = board / "Board" / "Tasks" / "Eng" / "ship-feature.md"
    fm, _, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert infer_lane(fm) == "done"
    assert unquote(fm.get("source", "")) == "agent"


def test_acme_task_lifecycle(acme: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(acme))
    plan_id = _register_and_plan(acme)
    assert (
        cli_main(
            [
                "task",
                "create",
                "--title",
                "Hello",
                "--project",
                "Eng",
                "--build",
                "--agent",
                "bot",
                "--plan-id",
                plan_id,
            ]
        )
        == 0
    )
    path = acme / "AcmeDemo" / "Tasks" / "Eng" / "hello.md"
    assert path.is_file()


def test_agent_skips_triage(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    plan_id = _register_and_plan(board)
    assert (
        cli_main(
            [
                "task",
                "create",
                "--title",
                "No triage",
                "--project",
                "Eng",
                "--source",
                "agent",
                "--lane",
                "triage",
                "--slug",
                "no-triage",
                "--agent",
                "bot",
                "--plan-id",
                plan_id,
            ]
        )
        == 0
    )
    path = board / "Board" / "Tasks" / "Eng" / "no-triage.md"
    fm, _, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert infer_lane(fm) != "triage"


def test_roadmap_sync_cannot_move_to_triage(
    board: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    assert (
        cli_main(
            [
                "task",
                "create",
                "--title",
                "Synced",
                "--project",
                "Eng",
                "--source",
                "roadmap-sync",
                "--lane",
                "backlog",
                "--slug",
                "synced",
            ]
        )
        == 0
    )
    assert cli_main(["task", "move", "synced", "--lane", "triage"]) == 1


def test_export(board: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    plan_id = _register_and_plan(board)
    cli_main(
        [
            "task",
            "create",
            "--title",
            "A",
            "--project",
            "Eng",
            "--lane",
            "backlog",
            "--agent",
            "bot",
            "--plan-id",
            plan_id,
        ]
    )
    assert cli_main(["export"]) == 0
    out = capsys.readouterr().out
    assert "## backlog" in out


def test_gate_status_cli(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    assert cli_main(["agent", "gate-status"]) == 1


def test_load_config(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    cfg = load_config()
    assert cfg.projects[0]["name"] == "Eng"
    assert cfg.board_dir == "Board"
    assert cfg.triage_enabled is True
