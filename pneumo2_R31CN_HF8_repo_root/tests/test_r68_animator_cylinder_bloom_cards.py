from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_camera_facing_bloom_cards_for_gas_chambers() -> None:
    for needle in (
        'self._cyl_bloom_card_meshes: List["gl.GLMeshItem"] = []',
        "def _camera_view_direction_local_xyz(",
        "def _cylinder_bloom_card_state(",
        "def _cylinder_bloom_card_face_colors(",
        "def _cylinder_bloom_card_rgba(",
        "camera_view_dir = self._camera_view_direction_local_xyz(target_xyz=np.asarray(center_draw, dtype=float)",
        "cap_bloom_state = self._cylinder_bloom_card_state(",
        "rod_bloom_state = self._cylinder_bloom_card_state(",
        "cap_bloom_face_colors = self._cylinder_bloom_card_face_colors(",
        "rod_bloom_face_colors = self._cylinder_bloom_card_face_colors(",
    ):
        assert needle in APP


def test_animator_source_maps_bloom_cards_to_cap_and_rod_meshes() -> None:
    for needle in (
        "*self._cyl_bloom_card_meshes",
        "self._cyl_bloom_card_meshes.append(bloom_card)",
        'key=f"{cyl_name}:{corner}:cap_bloom"',
        'key=f"{cyl_name}:{corner}:rod_bloom"',
        "_set_poly_mesh(",
        "face_colors_rgba_u8=cap_bloom_face_colors",
        "face_colors_rgba_u8=rod_bloom_face_colors",
        "self._invalidate_mesh(cap_bloom_item)",
        "self._invalidate_mesh(rod_bloom_item)",
    ):
        assert needle in APP
