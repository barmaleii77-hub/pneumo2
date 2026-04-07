from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_3d_speed_and_accel_arrows_use_solver_truth_channels_with_sign() -> None:
    assert 'def _solver_signed_speed_along_road(self, get_value) -> float:' in SRC
    assert 'def _solver_external_acceleration_xy(self, get_value) -> tuple[float, float]:' in SRC
    assert 'return float(get_value("скорость_vx_м_с", 0.0))' in SRC
    assert 'float(get_value("ускорение_продольное_ax_м_с2", 0.0))' in SRC
    assert 'float(get_value("ускорение_поперечное_ay_м_с2", 0.0))' in SRC
    assert 'ensure_body_velocity_xy()' not in SRC
    assert 'ensure_body_acceleration_xy()' not in SRC
    assert 'speed_along_road = self._solver_signed_speed_along_road(_g)' in SRC
    assert 'external_ax, external_ay = self._solver_external_acceleration_xy(_g)' in SRC


def test_3d_vector_overlay_ignores_heave_channels_for_user_facing_velocity_and_acceleration_arrows() -> None:
    assert 'np.asarray(R_local[:, 0], dtype=float) * float(speed_along_road * self._vel_scale)' in SRC
    assert 'np.asarray(R_local[:, 0], dtype=float) * float(external_ax * self._accel_scale)' in SRC
    assert '+ np.asarray(R_local[:, 1], dtype=float) * float(external_ay * self._accel_scale)' in SRC
