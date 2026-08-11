"""Tests for tag-along board discovery (solaris.toml) and doctor."""

from __future__ import annotations

from pathlib import Path

import pytest

from solaris.cli import main as cli_main
from solaris.core import (
    load_config,
    load_solaris_pointer,
    resolve_board_root,
)


@pytest.fixture()
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "Vault"
    root.mkdir()
    monkeypatch.delenv("BOARD_ROOT", raising=False)
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
                "--board-dir",
                "Board",
            ]
        )
        == 0
    )
    cfg = root / "Board" / "config.yml"
    text = cfg.read_text(encoding="utf-8")
    text += (
        "\nlinked_repos:\n"
        "  - id: app\n"
        f"    path: {tmp_path / 'App'}\n"
    )
    cfg.write_text(text, encoding="utf-8")
    return root


def test_resolve_via_solaris_toml(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    app = tmp_path / "App"
    app.mkdir()
    (app / "solaris.toml").write_text(
        f'board_root = "{vault}"\nrepo_id = "app"\n',
        encoding="utf-8",
    )
    resolved = resolve_board_root(app)
    assert resolved == vault.resolve()
    ptr = load_solaris_pointer(app / "solaris.toml")
    assert ptr.repo_id == "app"
    cfg = load_config(resolved)
    assert any(lr.id == "app" for lr in cfg.linked_repos)


def test_missing_pointer_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    # Walk-up may hit unreadable siblings under /tmp on CI; must not raise PermissionError.
    with pytest.raises(FileNotFoundError):
        resolve_board_root(empty)


def test_doctor_from_linked_repo(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    app = tmp_path / "App"
    app.mkdir()
    (app / "solaris.toml").write_text(
        f'board_root = "{vault}"\nrepo_id = "app"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(app)
    assert cli_main(["doctor"]) == 0


def test_init_vault_repo_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--vault-repo scaffolds a sibling vault; code root only gets solaris.toml (+ gates)."""
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    app = tmp_path / "MyApp"
    app.mkdir()
    (app / "src").mkdir()
    (app / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    assert (
        cli_main(
            [
                "init",
                "--vault-repo",
                "--obsidian",
                "--root",
                str(app),
                "--name",
                "MyApp",
                "--project",
                "Eng",
                "--repo-id",
                "myapp",
            ]
        )
        == 0
    )

    vault = tmp_path / "MyApp-vault"
    assert vault.is_dir()
    assert (vault / "Board" / "config.yml").is_file()
    assert (vault / ".obsidian").is_dir()
    assert (vault / ".git").exists()
    assert (vault / "README.md").is_file()
    assert not (app / "Board").exists()
    assert not (app / ".obsidian").exists()
    assert (app / "solaris.toml").is_file()
    assert (app / "src" / "main.py").is_file()

    cfg = load_config(vault)
    assert any(lr.id == "myapp" and lr.path == app.resolve() for lr in cfg.linked_repos)
    ptr = load_solaris_pointer(app / "solaris.toml")
    assert ptr.board_root == vault.resolve()
    assert ptr.repo_id == "myapp"
    assert resolve_board_root(app) == vault.resolve()

    monkeypatch.chdir(app)
    assert cli_main(["doctor"]) == 0


def test_init_vault_repo_custom_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BOARD_ROOT", raising=False)
    app = tmp_path / "Code"
    app.mkdir()
    custom = tmp_path / "elsewhere" / "vault-x"
    assert (
        cli_main(
            [
                "init",
                "--vault-repo",
                "--root",
                str(app),
                "--vault-path",
                str(custom),
                "--name",
                "X",
                "--board-dir",
                "Board",
            ]
        )
        == 0
    )
    assert (custom / "Board" / "config.yml").is_file()
    assert "board_root" in (app / "solaris.toml").read_text(encoding="utf-8")
