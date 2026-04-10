from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_registers_custom_scene_shaders_for_fast_cinematic_lighting() -> None:
    for needle in (
        '_ANIMATOR_SOLID_SHADER = "animatorDualLight"',
        '_ANIMATOR_ROAD_SHADER = "animatorRoadGloss"',
        "def _register_animator_custom_shaders() -> None:",
        "shader_mod.ShaderProgram(",
        "_ANIMATOR_CUSTOM_SHADERS_REGISTERED = True",
        "def _animator_shader_name(preferred: Optional[str], fallback: Optional[str]) -> Optional[str]:",
        "_register_animator_custom_shaders()",
    ):
        assert needle in APP


def test_animator_source_uses_custom_scene_shaders_for_road_and_solid_meshes() -> None:
    for needle in (
        'self.view.setBackgroundColor(6, 10, 18)',
        'shader=_animator_shader_name(_ANIMATOR_ROAD_SHADER, "shaded")',
        'shader=_animator_shader_name(_ANIMATOR_SOLID_SHADER, "edgeHilight")',
        'shader=_animator_shader_name(_ANIMATOR_SOLID_SHADER, "shaded")',
        "edgeColor=(0.40, 0.55, 0.72, 0.88)",
        "edgeColor=(0.86, 0.92, 0.98, 0.78)",
        "edgeColor=(0.56, 0.76, 0.98, 0.60)",
    ):
        assert needle in APP
