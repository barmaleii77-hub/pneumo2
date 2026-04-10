from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_wheel_spin_phase_helpers() -> None:
    for needle in (
        "def _wheel_spin_phase_rad(",
        "spin_phase_rad: float = 0.0,",
        "theta = np.arctan2(z, x) - float(spin_phase_rad)",
        'return float(math.fmod(progress / radius, 2.0 * np.pi))',
    ):
        assert needle in APP


def test_animator_source_drives_tire_and_rim_animation_from_path_progress() -> None:
    for needle in (
        "s_progress_m = float(",
        "np.asarray(b.ensure_s_world(), dtype=float)",
        "wheel_spin_phase = self._wheel_spin_phase_rad(",
        "path_progress_m=s_progress_m,",
        "speed_m_s=float(speed_along_road),",
        "spin_phase_rad=float(wheel_spin_phase),",
        "rim_verts, rim_faces = self._wheel_rim_mesh(",
        "wheel_face_colors = self._wheel_tire_face_colors(",
    ):
        assert needle in APP
