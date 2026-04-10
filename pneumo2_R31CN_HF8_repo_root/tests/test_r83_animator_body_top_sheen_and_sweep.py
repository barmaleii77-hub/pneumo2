from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_body_top_sheen_and_sweep_layers() -> None:
    for needle in (
        'self._body_top_sheen_mesh: Optional["gl.GLMeshItem"] = None',
        'self._body_top_sweep_line: Optional["gl.GLLinePlotItem"] = None',
        "def _body_top_sheen_rgba(",
        "def _body_top_sheen_face_colors(",
        "def _body_top_sweep_rgba(",
        "self._body_top_sheen_mesh = gl.GLMeshItem(",
        "self._body_top_sweep_line = gl.GLLinePlotItem(",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_body_top_runtime() -> None:
    for needle in (
        "roof_face_colors = self._body_top_sheen_face_colors(",
        'key="body-top-sheen-scene-grade"',
        "roof_sweep_rgba = self._body_top_sweep_rgba(",
        'key="body-top-sweep-scene-grade"',
        "self._body_top_sweep_line.setData(pos=sweep_vertices, color=roof_sweep_colors)",
    ):
        assert needle in APP
