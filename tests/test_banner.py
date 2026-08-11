"""CLI brand banner."""

from __future__ import annotations

from solaris.banner import render_banner


def test_plain_banner_includes_version():
    text = render_banner("9.9.9", color=False)
    assert "(*) solaris" in text
    assert "v9.9.9" in text
    assert "solaris init" in text


def test_color_banner_has_ansi_when_forced():
    text = render_banner("0.1.6", color=True)
    assert "\033[" in text
    assert "v0.1.6" in text
