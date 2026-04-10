from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_front_bow_wave_layers() -> None:
    for needle in (
        'self._front_bow_wave_meshes: List["gl.GLMeshItem"] = []',
        "def _front_bow_wave_rgba(",
        "def _front_bow_wave_face_colors(",
        "self._front_bow_wave_meshes.append(bow)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_front_bow_wave_runtime() -> None:
    for needle in (
        "bow_face_colors = self._front_bow_wave_face_colors(",
        'key=f"front-bow-wave-scene-grade-{bow_idx}"',
        "bow_rgba = self._front_bow_wave_rgba(",
        "bow_item = self._front_bow_wave_meshes[bow_idx] if bow_idx < len(self._front_bow_wave_meshes) else None",
    ):
        assert needle in APP
