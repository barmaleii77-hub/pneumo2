from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_cinematic_reflection_and_wheel_glint_layers() -> None:
    for needle in (
        'self._wheel_crown_glint_lines: List["gl.GLLinePlotItem"] = []',
        'self._contact_reflection_meshes: List["gl.GLMeshItem"] = []',
        "def _wheel_crown_glint_rgba(",
        "def _road_reflection_face_colors(",
        "def _road_reflection_rgba(",
        "self._wheel_crown_glint_lines.append(crown_glint)",
        "self._contact_reflection_meshes.append(reflection)",
    ):
        assert needle in APP


def test_animator_source_uses_scene_grade_for_reflections_and_crown_glints() -> None:
    for needle in (
        "crown_glint_item = self._wheel_crown_glint_lines[idx]",
        "crown_glint_rgba = self._wheel_crown_glint_rgba(",
        'key=f"wheel-crown-glint-scene-{corners[idx]}"',
        "reflection_item = self._contact_reflection_meshes[idx]",
        "reflection_face_colors = self._road_reflection_face_colors(",
        "reflection_face_rgba = self._road_reflection_rgba(",
        'key=f"road-reflection-scene-grade-{corners[idx]}-{idx}"',
    ):
        assert needle in APP
