from __future__ import annotations

from pathlib import Path


def test_root_app_release_uses_release_info_and_not_stale_r176() -> None:
    src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'RELEASE = os.environ.get("PNEUMO_RELEASE") or "PneumoApp_v6_80_R176"' not in src
    assert "from pneumo_solver_ui.release_info import get_release" in src
    assert "RELEASE = get_release()" in src
