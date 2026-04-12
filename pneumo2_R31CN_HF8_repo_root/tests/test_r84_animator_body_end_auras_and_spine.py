from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_body_end_auras_and_spine_layers() -> None:
    for needle in (
        'self._body_end_aura_meshes: List["gl.GLMeshItem"] = []',
        'self._body_spine_line: Optional["gl.GLLinePlotItem"] = None',
        "def _body_end_aura_rgba(",
        "def _body_end_aura_face_colors(",
        "def _body_spine_rgba(",
        "self._body_end_aura_meshes.append(aura)",
        "self._body_spine_line = gl.GLLinePlotItem(",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_body_end_auras_and_spine_runtime() -> None:
    for needle in (
        "aura_face_colors = self._body_end_aura_face_colors(",
        'key=f"body-end-aura-scene-grade-{aura_idx}"',
        "spine_rgba = self._body_spine_rgba(",
        'key="body-spine-highlight-scene-grade"',
        "_set_line_item_data(self._body_spine_line, spine_vertices, colors_rgba=spine_colors)",
    ):
        assert needle in APP
