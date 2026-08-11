"""Solaris CLI brand banner (printed on first-time init)."""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

# Palette matches Solaris logo/cli logo (10G): gold · ember · muted · bone
_GOLD = "\033[38;5;221m"
_EMBER = "\033[38;5;209m"
_MUTED = "\033[38;5;138m"
_BONE = "\033[38;5;250m"
_RESET = "\033[0m"


def _want_color(*, color: bool | None = None, stream=None) -> bool:
    if color is not None:
        return color
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def _plain_banner(version: str) -> str:
    """Plain text; prefer packaged .txt with version substituted."""
    text = _load_banner_txt()
    if text:
        # Design file hardcodes v1.0.0 — swap in package version.
        out = text.replace("v1.0.0", f"v{version}")
        return out.rstrip("\n")
    return f"  (*) solaris  v{version}\n  > solaris init --star polaris"


def _load_banner_txt() -> str | None:
    here = Path(__file__).resolve().parent / "data" / "cli" / "solaris-banner.txt"
    if here.is_file():
        return here.read_text(encoding="utf-8")
    try:
        packaged = resources.files("solaris").joinpath("data/cli/solaris-banner.txt")
        return packaged.read_text(encoding="utf-8")
    except Exception:
        return None


def render_banner(version: str | None = None, *, color: bool | None = None) -> str:
    """Return the CLI banner string (optionally ANSI-colored)."""
    if version is None:
        from solaris import __version__

        version = __version__
    if not _want_color(color=color):
        return _plain_banner(version)
    return "\n".join(
        [
            f"  {_GOLD}(*) solaris{_RESET}  {_MUTED}v{version}{_RESET}",
            f"  {_EMBER}>{_RESET} {_BONE}solaris init --star polaris{_RESET}",
        ]
    )


def print_banner(version: str | None = None, *, color: bool | None = None, file=None) -> None:
    """Print banner + blank line (safe for non-TTY / NO_COLOR)."""
    file = file or sys.stdout
    print(render_banner(version, color=color), file=file)
    print(file=file)
