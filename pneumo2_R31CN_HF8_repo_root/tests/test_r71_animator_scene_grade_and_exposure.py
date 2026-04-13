from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_scene_grade_helpers_and_runtime_profile() -> None:
    for needle in (
        'self._scene_scalar_visual_state: Dict[str, float] = {}',
        "def _smooth_scalar(",
        "def _scene_grade_profile(",
        "def _scene_grade_color_array(",
        "def _scene_grade_rgba_scalar(",
        "def _scene_graded_rgba(",
        "scene_glass_energy_us: list[float] = []",
        "scene_glass_energy_u = float(",
        'key_prefix="scene-grade-base"',
        "scene_grade_base = self._effective_scene_grade_profile(",
        'key="scene-background"',
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_glass_road_and_atmosphere_passes() -> None:
    for needle in (
        "cap_pressure_u = self._cylinder_pressure_visual_u(",
        "rod_pressure_u = self._cylinder_pressure_visual_u(",
        "cap_bloom_face_rgba = self._scene_graded_rgba(",
        "rod_bloom_face_rgba = self._scene_graded_rgba(",
        "cap_glint_rgba = self._scene_graded_rgba(",
        "rod_caustic_rgba = self._scene_graded_rgba(",
        "road_face_colors = self._scene_grade_color_array(",
        "edge_colors = self._scene_grade_color_array(",
        "stripe_colors = self._scene_grade_color_array(",
        "patch_face_colors = self._scene_grade_color_array(",
        "fog_face_colors = self._scene_grade_color_array(",
        "fog_face_rgba = self._scene_graded_rgba(",
        "glaze_face_colors = self._scene_grade_color_array(",
        "accent_rgba = self._scene_graded_rgba(",
        "key_light_rgba = self._scene_graded_rgba(",
        "shaft_face_colors = self._scene_grade_color_array(",
        "focus_face_colors = self._scene_grade_color_array(",
        "focus_rgba = self._scene_graded_rgba(",
    ):
        assert needle in APP
