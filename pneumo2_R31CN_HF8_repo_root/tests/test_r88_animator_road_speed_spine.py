from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_road_speed_spine_layer() -> None:
    for needle in (
        'self._road_speed_spine_mesh: Optional["gl.GLMeshItem"] = None',
        "def _road_speed_spine_rgba(",
        "def _road_speed_spine_face_colors(",
        "self._road_speed_spine_mesh = gl.GLMeshItem(",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_road_speed_spine_runtime() -> None:
    for needle in (
        "spine_face_colors = self._road_speed_spine_face_colors(",
        'key="road-speed-spine-scene-grade"',
        "spine_rgba = self._road_speed_spine_rgba(",
        "if self._road_speed_spine_mesh is not None:",
    ):
        assert needle in APP
