from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_speed_corridor_layers() -> None:
    for needle in (
        'self._speed_corridor_meshes: List["gl.GLMeshItem"] = []',
        "def _speed_corridor_rgba(",
        "def _speed_corridor_face_colors(",
        "self._speed_corridor_meshes.append(corridor)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_speed_corridor_runtime() -> None:
    for needle in (
        "corridor_face_colors = self._speed_corridor_face_colors(",
        'key=f"speed-corridor-scene-grade-{corridor_idx}"',
        "corridor_rgba = self._speed_corridor_rgba(",
        "corridor_item = self._speed_corridor_meshes[corridor_idx] if corridor_idx < len(self._speed_corridor_meshes) else None",
    ):
        assert needle in APP
