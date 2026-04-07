from __future__ import annotations

from pathlib import Path


def test_active_app_release_uses_release_info_and_not_stale_r53() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    assert "APP_RELEASE = \"R53\"" not in src
    assert "from pneumo_solver_ui.release_info import get_release" in src
    assert "APP_RELEASE = get_release()" in src
