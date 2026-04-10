from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_material_helpers_and_rich_scene_meshes() -> None:
    for needle in (
        "_schlick_f0_from_ior",
        "_road_face_colors(",
        "_line_color_ramp(",
        "_animator_shader_name(",
        "_body_shadow_mesh",
        "_wheel_shadow_meshes",
        "_wheel_hub_meshes",
        "_arm_lower_meshes",
        "_arm_upper_meshes",
        'shader="balloon"',
        'shader=_animator_shader_name(_ANIMATOR_SOLID_SHADER, "edgeHilight")',
        "ellipse_mesh_on_plane as _ellipse_mesh_on_plane",
    ):
        assert needle in APP


def test_animator_source_upgrades_arrow_glow_and_heatmap_palette() -> None:
    for needle in (
        "self.glow_body = QtWidgets.QGraphicsLineItem()",
        "self.glow_head = QtWidgets.QGraphicsPolygonItem()",
        "def _apply_glow_style(",
        "def _palette_rgb(",
        "Premium heat palette",
        "QLinearGradient(frame.topLeft(), frame.bottomLeft())",
        "QRadialGradient(",
    ):
        assert needle in APP
