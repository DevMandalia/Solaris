"""End-to-end smoke for init → create → move → export."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from solaris.cli import main as cli_main
from solaris.core import infer_lane, load_config, parse_frontmatter, unquote


@pytest.fixture()
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BOARD_ROOT", str(tmp_path))
    assert cli_main(["init", "--root", str(tmp_path), "--name", "Demo", "--project", "Eng"]) == 0
    assert (tmp_path / "Board" / "config.yml").is_file()
    return tmp_path


def test_init_has_no_instance_leaks(board: Path) -> None:
    text = ""
    for p in (board / "Board" / "_system").rglob("*.md"):
        text += p.read_text(encoding="utf-8")
    for bad in ("Dragonstone", "Polaris", "Sauna", "Personal", "G&A"):
        assert bad not in text, bad


def test_task_lifecycle(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
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


def test_agent_skips_triage(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
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
    cli_main(["task", "create", "--title", "A", "--project", "Eng", "--lane", "backlog"])
    assert cli_main(["export"]) == 0
    out = capsys.readouterr().out
    assert "## backlog" in out


def test_load_config(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_ROOT", str(board))
    cfg = load_config()
    assert cfg.projects[0]["name"] == "Eng"
    assert cfg.triage_enabled is True
