"""OS sidecar files next to board markdown must be skipped, never fatal.

macOS writes an AppleDouble `._<name>` beside every file it touches on exFAT /
FAT / SMB volumes (USB sticks, network shares). The sidecar keeps the `.md`
suffix but holds binary metadata, so a naive `*.md` scan aborts the whole CLI
with UnicodeDecodeError. Finder's `.DS_Store` is the same class of junk.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from solaris.cli import main as cli_main
from solaris.core import (
    find_agent_plan,
    is_board_markdown,
    iter_board_markdown,
    iter_task_files,
    load_config,
    read_board_text,
    set_active_sprint,
)

# AppleDouble magic (00 05 16 07) followed by bytes that are not valid UTF-8.
APPLEDOUBLE = b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        \x00\x02\x00\x00\x00\x09\xb0\xff"
DS_STORE = b"\x00\x00\x00\x01Bud1\x00\x00\x10\x00\xb0\xff"


@pytest.fixture()
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A board with one registered agent, one open plan, and one real card."""
    root = tmp_path / "SidecarRepo"
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
    assert (
        cli_main(
            [
                "task",
                "create",
                "--title",
                "Real card",
                "--project",
                "Eng",
                "--lane",
                "backlog",
                "--agent",
                "bot",
                "--plan-id",
                "smoke-plan",
            ]
        )
        == 0
    )
    return root


def _plant_sidecars(root: Path) -> list[Path]:
    """Drop binary sidecars next to the real card, the plan, and the agent profile."""
    cfg = load_config()
    card = root / "Board" / "Tasks" / "Eng" / "real-card.md"
    assert card.is_file()
    plan = find_agent_plan(cfg, "smoke-plan")
    assert plan is not None
    agent = cfg.agents_dir / "bot.md"
    assert agent.is_file()

    planted: list[Path] = []
    for real in (card, plan, agent):
        side = real.with_name(f"._{real.name}")
        side.write_bytes(APPLEDOUBLE)
        planted.append(side)
    ds_store = card.parent / ".DS_Store"
    ds_store.write_bytes(DS_STORE)
    planted.append(ds_store)
    return planted


def test_predicate_rejects_sidecars() -> None:
    assert is_board_markdown(Path("card.md"))
    assert is_board_markdown(Path("Card.MD"))
    assert not is_board_markdown(Path("._card.md"))
    assert not is_board_markdown(Path(".DS_Store"))
    assert not is_board_markdown(Path("notes.txt"))


def test_iter_board_markdown_skips_sidecars(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "sub" / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "._a.md").write_bytes(APPLEDOUBLE)
    (tmp_path / "sub" / "._b.md").write_bytes(APPLEDOUBLE)
    (tmp_path / ".DS_Store").write_bytes(DS_STORE)

    assert [p.name for p in iter_board_markdown(tmp_path)] == ["a.md", "b.md"]
    assert [p.name for p in iter_board_markdown(tmp_path, recursive=False)] == ["a.md"]
    assert iter_board_markdown(tmp_path / "missing") == []
    # The slug-collision set in `task create` is built from these stems.
    assert {p.stem for p in iter_board_markdown(tmp_path, recursive=False)} == {"a"}


def test_read_board_text_warns_and_skips(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bad = tmp_path / "broken.md"
    bad.write_bytes(APPLEDOUBLE)
    assert read_board_text(bad) is None
    err = capsys.readouterr().err
    assert "warning: skipping unreadable file" in err
    assert "broken.md" in err

    assert read_board_text(tmp_path / "missing.md") is None

    good = tmp_path / "good.md"
    good.write_text("ok", encoding="utf-8")
    assert read_board_text(good) == "ok"


def test_iter_task_files_skips_sidecars(board: Path) -> None:
    planted = _plant_sidecars(board)
    found = iter_task_files(load_config())
    assert [p.name for p in found] == ["real-card.md"]
    assert not set(planted) & set(found)


def test_task_list_ignores_sidecars(board: Path, capsys: pytest.CaptureFixture) -> None:
    _plant_sidecars(board)
    assert cli_main(["task", "list"]) == 0
    out, err = capsys.readouterr()
    assert "Real card" in out
    assert "._" not in out
    assert "# 1 tasks" in err
    assert "warning" not in err

    assert cli_main(["task", "list", "--project", "Eng"]) == 0
    out, err = capsys.readouterr()
    assert "Real card" in out
    assert "# 1 tasks" in err


def test_export_ignores_sidecars(board: Path, capsys: pytest.CaptureFixture) -> None:
    _plant_sidecars(board)
    assert cli_main(["export"]) == 0
    out, err = capsys.readouterr()
    assert "Real card" in out
    assert "._" not in out
    assert "warning" not in err


def test_agent_list_ignores_sidecars(board: Path, capsys: pytest.CaptureFixture) -> None:
    _plant_sidecars(board)
    assert cli_main(["agent", "list", "--plans", "--open"]) == 0
    out, err = capsys.readouterr()
    assert "smoke-plan" in out
    assert "._" not in out
    assert "# 1 plans" in err
    assert "warning" not in err

    assert cli_main(["agent", "list"]) == 0
    out, err = capsys.readouterr()
    assert "bot" in out
    assert "._" not in out
    assert "# 1 agents" in err
    assert "warning" not in err


def test_gate_status_survives_sidecars(board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant_sidecars(board)
    monkeypatch.chdir(board)
    # Rules are unread so the gate reports not-ready (1); it must not raise.
    assert cli_main(["agent", "gate-status"]) in (0, 1)


def test_sync_rollover_rollup_survive_sidecars(
    board: Path, capsys: pytest.CaptureFixture
) -> None:
    _plant_sidecars(board)
    assert cli_main(["sync"]) == 0
    assert cli_main(["rollup", "--dry-run", "--force"]) == 0
    # Rollover only scans tasks when the stored sprint is behind the calendar.
    last_week = (date.today() - timedelta(weeks=1)).strftime("%G-W%V")
    set_active_sprint(load_config(), last_week)
    assert cli_main(["rollover", "--dry-run", "--force"]) == 0
    out, err = capsys.readouterr()
    assert "._" not in out
    assert "warning" not in err


def test_undecodable_card_is_skipped_with_warning(
    board: Path, capsys: pytest.CaptureFixture
) -> None:
    """A real `.md` that is not UTF-8 is skipped with a warning, not fatal."""
    corrupt = board / "Board" / "Tasks" / "Eng" / "corrupt.md"
    corrupt.write_bytes(b"---\ntype: task\ntitle: Corrupt\n---\n\xb0\xff")

    assert cli_main(["task", "list"]) == 0
    out, err = capsys.readouterr()
    assert "Real card" in out
    assert "corrupt.md" not in out
    assert "warning: skipping unreadable file" in err
    assert "corrupt.md" in err

    assert cli_main(["export"]) == 0
    out, err = capsys.readouterr()
    assert "Real card" in out
    assert "corrupt.md" in err
