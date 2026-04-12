from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_underbody_and_body_silhouette_layers() -> None:
    for needle in (
        'self._underbody_glow_mesh: Optional["gl.GLMeshItem"] = None',
        'self._body_silhouette_line: Optional["gl.GLLinePlotItem"] = None',
        "def _underbody_glow_rgba(",
        "def _underbody_glow_face_colors(",
        "def _body_silhouette_rgba(",
        "self._underbody_glow_mesh = gl.GLMeshItem(",
        "self._body_silhouette_line = gl.GLLinePlotItem(",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_underbody_and_body_rim_runtime() -> None:
    for needle in (
        "underbody_face_colors = self._underbody_glow_face_colors(",
        'key="underbody-glow-scene-grade"',
        "if self._underbody_glow_mesh is not None:",
        "_set_line_item_data(self._body_silhouette_line, silhouette_vertices, colors_rgba=body_rim_colors)",
        'key="body-silhouette-rim-scene-grade"',
    ):
        assert needle in APP
