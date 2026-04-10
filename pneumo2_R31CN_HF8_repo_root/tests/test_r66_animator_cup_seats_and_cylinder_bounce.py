from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_builds_cup_like_spring_seat_meshes() -> None:
    for needle in (
        "def _spring_seat_cup_mesh(",
        "opening_normal_xyz: np.ndarray",
        "rings_spec = [",
        '"seat_inner_radius_m": float(',
        "top_seat_verts, top_seat_faces = self._spring_seat_cup_mesh(",
        "bot_seat_verts, bot_seat_faces = self._spring_seat_cup_mesh(",
        "opening_normal_xyz=spring_axis_unit",
        "opening_normal_xyz=-spring_axis_unit",
        "_set_poly_mesh(top_seat_mesh, top_seat_verts, top_seat_faces)",
        "_set_poly_mesh(bot_seat_mesh, bot_seat_verts, bot_seat_faces)",
    ):
        assert needle in APP


def test_animator_source_adds_bounce_light_to_cylinder_housings() -> None:
    for needle in (
        'key=f"cyl-body-{cyl_name}-{corner}"',
        "cyl_body_face_rgba, cyl_body_edge_rgba = self._contact_bounce_material_rgba(",
        "face_rgba=cyl_body_face_rgba",
        "edge_rgba=cyl_body_edge_rgba",
        "gain=0.46",
    ):
        assert needle in APP
