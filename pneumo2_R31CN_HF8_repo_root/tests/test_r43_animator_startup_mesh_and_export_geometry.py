from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.data_contract import supplement_animator_geometry_meta

ROOT = Path(__file__).resolve().parents[1]


def test_supplement_animator_geometry_meta_derives_road_width_from_track_and_wheel_width() -> None:
    geom = supplement_animator_geometry_meta({"track_m": 1.0, "wheel_width_m": 0.22})
    assert geom["road_width_m"] == 1.22


def test_supplement_animator_geometry_meta_preserves_explicit_positive_road_width() -> None:
    geom = supplement_animator_geometry_meta({"track_m": 1.0, "wheel_width_m": 0.22, "road_width_m": 1.5})
    assert geom["road_width_m"] == 1.5


def test_desktop_animator_startup_uses_empty_meshdata_for_road_and_contact_patch() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    assert 'self._road_mesh = gl.GLMeshItem(\n            meshdata=self._empty_meshdata(),' in src
    assert 'self._contact_patch_mesh = gl.GLMeshItem(\n            meshdata=self._empty_meshdata(),' in src
    assert 'AA_EnableHighDpiScaling' not in src
    assert 'AA_UseHighDpiPixmaps' not in src
