from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_axle_wash_layers() -> None:
    for needle in (
        'self._axle_wash_meshes: List["gl.GLMeshItem"] = []',
        "def _axle_wash_rgba(",
        "def _axle_wash_face_colors(",
        "self._axle_wash_meshes.append(axle)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_axle_wash_runtime() -> None:
    for needle in (
        "axle_face_colors = self._axle_wash_face_colors(",
        'key=f"axle-wash-scene-grade-{axle_idx}"',
        "axle_rgba = self._axle_wash_rgba(",
        "axle_item = self._axle_wash_meshes[axle_idx] if axle_idx < len(self._axle_wash_meshes) else None",
    ):
        assert needle in APP
