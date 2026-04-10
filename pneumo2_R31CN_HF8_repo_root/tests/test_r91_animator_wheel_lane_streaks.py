from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_wheel_lane_streak_layers() -> None:
    for needle in (
        'self._wheel_lane_streak_meshes: List["gl.GLMeshItem"] = []',
        "def _wheel_lane_streak_rgba(",
        "def _wheel_lane_streak_face_colors(",
        "self._wheel_lane_streak_meshes.append(lane)",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_wheel_lane_streak_runtime() -> None:
    for needle in (
        "lane_face_colors = self._wheel_lane_streak_face_colors(",
        'key=f"wheel-lane-streak-scene-grade-{lane_idx}"',
        "lane_rgba = self._wheel_lane_streak_rgba(",
        "lane_item = self._wheel_lane_streak_meshes[lane_idx] if lane_idx < len(self._wheel_lane_streak_meshes) else None",
    ):
        assert needle in APP
