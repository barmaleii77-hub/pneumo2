from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_soft_shadow_face_colors_and_colored_poly_mesh_support() -> None:
    for needle in (
        "def _wheel_shadow_face_colors(",
        "def _set_poly_mesh(",
        "face_colors_rgba_u8: Optional[np.ndarray] = None",
        'mesh_kwargs["faceColors"] = face_cols',
        "self._apply_mesh_material(",
        "self._body_shadow_mesh,",
    ):
        assert needle in APP


def test_animator_source_makes_wheel_shadows_load_and_gap_aware() -> None:
    for needle in (
        "tire_forces_n = [",
        "mean_tire_force_n = float(np.nanmean(np.asarray(tire_forces_n, dtype=float)))",
        "wheel_gap_m = float(",
        "shadow_radius_u = max(0.05, wheel_radius_m * (0.62 + 0.18 * load_u + 0.24 * gap_u))",
        "shadow_radius_v = max(0.03, wheel_width_m * (0.52 + 0.16 * load_u + 0.20 * gap_u))",
        "shadow_face_colors = self._wheel_shadow_face_colors(",
        "face_colors_rgba_u8=shadow_face_colors",
    ):
        assert needle in APP
