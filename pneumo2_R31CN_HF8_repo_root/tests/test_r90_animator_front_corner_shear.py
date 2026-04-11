from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_front_corner_shear_layers() -> None:
    for needle in (
        'self._front_corner_shear_meshes: List["gl.GLMeshItem"] = []',
        "def _front_corner_shear_rgba(",
        "def _front_corner_shear_face_colors(",
        "self._front_corner_shear_meshes.append(shear)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_front_corner_shear_runtime() -> None:
    for needle in (
        "shear_face_colors = self._front_corner_shear_face_colors(",
        'key=f"front-corner-shear-scene-grade-{shear_idx}"',
        "shear_rgba = self._front_corner_shear_rgba(",
        "shear_item = self._front_corner_shear_meshes[shear_idx] if shear_idx < len(self._front_corner_shear_meshes) else None",
    ):
        assert needle in APP
