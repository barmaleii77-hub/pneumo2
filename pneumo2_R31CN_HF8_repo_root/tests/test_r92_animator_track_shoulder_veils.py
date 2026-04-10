from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_track_shoulder_layers() -> None:
    for needle in (
        'self._track_shoulder_meshes: List["gl.GLMeshItem"] = []',
        "def _track_shoulder_rgba(",
        "def _track_shoulder_face_colors(",
        "self._track_shoulder_meshes.append(shoulder)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_track_shoulder_runtime() -> None:
    for needle in (
        "shoulder_face_colors = self._track_shoulder_face_colors(",
        'key=f"track-shoulder-scene-grade-{shoulder_idx}"',
        "shoulder_rgba = self._track_shoulder_rgba(",
        "shoulder_item = self._track_shoulder_meshes[shoulder_idx] if shoulder_idx < len(self._track_shoulder_meshes) else None",
    ):
        assert needle in APP
