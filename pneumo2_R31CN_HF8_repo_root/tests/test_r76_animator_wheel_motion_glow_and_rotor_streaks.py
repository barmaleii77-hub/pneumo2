from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_wheel_motion_overlay_layers_and_helpers() -> None:
    for needle in (
        'self._wheel_spin_glow_lines: List["gl.GLLinePlotItem"] = []',
        'self._wheel_rotor_streak_lines: List["gl.GLLinePlotItem"] = []',
        "def _wheel_spin_arc_vertices(",
        "def _wheel_spin_glow_rgba(",
        "def _wheel_rotor_streak_rgba(",
        "*self._wheel_spin_glow_lines",
        "*self._wheel_rotor_streak_lines",
        "self._wheel_spin_glow_lines.append(spin_glow)",
        "self._wheel_rotor_streak_lines.append(rotor_streak)",
    ):
        assert needle in APP


def test_animator_source_drives_spin_glow_and_rotor_streaks_from_wheel_phase() -> None:
    for needle in (
        "spin_glow_item = self._wheel_spin_glow_lines[idx] if idx < len(self._wheel_spin_glow_lines) else None",
        "rotor_streak_item = self._wheel_rotor_streak_lines[idx] if idx < len(self._wheel_rotor_streak_lines) else None",
        "spin_glow_vertices = self._wheel_spin_arc_vertices(",
        "spin_glow_rgba = self._wheel_spin_glow_rgba(",
        "rotor_streak_vertices = self._wheel_spin_arc_vertices(",
        "rotor_streak_rgba = self._wheel_rotor_streak_rgba(",
        "_set_colored_line_item(",
        'key=f"wheel-spin-glow-{corners[idx]}"',
        'key=f"wheel-rotor-streak-{corners[idx]}"',
        "for line_idx in range(len(wheel_pose_centers), len(self._wheel_spin_glow_lines)):",
        "for line_idx in range(len(wheel_pose_centers), len(self._wheel_rotor_streak_lines)):",
    ):
        assert needle in APP
