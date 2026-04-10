from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_spring_seat_meshes_and_runtime_alignment() -> None:
    for needle in (
        'self._spring_seat_meshes: List["gl.GLMeshItem"] = []',
        "*self._spring_seat_meshes",
        "spring_seat = gl.GLMeshItem(",
        "self._spring_seat_meshes.append(spring_seat)",
        '"seat_radius_m": float(max(0.028, coil_radius_m + 1.55 * wire_radius_m))',
        '"seat_thickness_m": float(max(0.0055, min(0.022, 1.90 * wire_radius_m)))',
        'seat_base = 2 * spring_idx',
        "top_seat_verts, top_seat_faces = self._spring_seat_cup_mesh(",
        "bot_seat_verts, bot_seat_faces = self._spring_seat_cup_mesh(",
    ):
        assert needle in APP


def test_animator_source_adds_contact_bounce_light_to_hubs_and_lower_arms() -> None:
    for needle in (
        "def _contact_bounce_material_rgba(",
        "lower_arm_corner_ids = _segment_corner_ids_from_quads(",
        "lower_arm_base_face_rgba = (0.24, 0.40, 0.58, 0.93)",
        'key=f"lower-arm-{corners[corner_idx]}-{seg_idx}"',
        'key=f"wheel-hub-{corners[idx]}"',
        'key=f"spring-seat-{spring_state[\'cyl_name\']}-{spring_state[\'corner\']}-bot"',
        "wheel_gap_m=float(corner_wheel_gap_m[idx]) if idx < len(corner_wheel_gap_m) else 0.0",
    ):
        assert needle in APP
