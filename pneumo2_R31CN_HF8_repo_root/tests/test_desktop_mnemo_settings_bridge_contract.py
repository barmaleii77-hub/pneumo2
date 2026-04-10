from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_settings_bridge_reads_view_mode_and_falls_back(tmp_path: Path) -> None:
    from pneumo_solver_ui.desktop_mnemo.settings_bridge import (
        desktop_mnemo_settings_path,
        desktop_mnemo_view_mode_label,
        normalize_desktop_mnemo_view_mode,
        read_desktop_mnemo_view_mode,
    )

    assert desktop_mnemo_settings_path(tmp_path) == (
        tmp_path / "pneumo_solver_ui" / "workspace" / "desktop_animator_settings.ini"
    )
    assert normalize_desktop_mnemo_view_mode("overview") == "overview"
    assert normalize_desktop_mnemo_view_mode("anything_else") == "focus"
    assert desktop_mnemo_view_mode_label("overview") == "Полная схема"
    assert desktop_mnemo_view_mode_label("focus") == "Фокусный сценарий"
    assert read_desktop_mnemo_view_mode(tmp_path) == "focus"

    ini_path = desktop_mnemo_settings_path(tmp_path)
    ini_path.parent.mkdir(parents=True, exist_ok=True)
    ini_path.write_text("[desktop_mnemo]\nview_mode=overview\n", encoding="utf-8")

    assert read_desktop_mnemo_view_mode(tmp_path) == "overview"
