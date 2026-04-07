from __future__ import annotations

from pathlib import Path


def test_suspension_geometry_treats_wheel_coord_as_mode_not_numeric() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "suspension_geometry_ui.py").read_text(encoding="utf-8")

    assert "def _normalize_wheel_coord_mode" in src
    assert 'float(base0.get("колесо_координата"' not in src
    assert 'params["колесо_координата"] = str(wheel_coord_mode)' in src
    assert 'Режим `колесо_координата`' in src
