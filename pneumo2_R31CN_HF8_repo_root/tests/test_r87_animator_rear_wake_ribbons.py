from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_rear_wake_layers() -> None:
    for needle in (
        'self._rear_wake_meshes: List["gl.GLMeshItem"] = []',
        "def _rear_wake_rgba(",
        "def _rear_wake_face_colors(",
        "self._rear_wake_meshes.append(wake)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_rear_wake_runtime() -> None:
    for needle in (
        "wake_face_colors = self._rear_wake_face_colors(",
        'key=f"rear-wake-scene-grade-{wake_idx}"',
        "wake_rgba = self._rear_wake_rgba(",
        "wake_item = self._rear_wake_meshes[wake_idx] if wake_idx < len(self._rear_wake_meshes) else None",
    ):
        assert needle in APP
