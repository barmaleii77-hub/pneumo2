from __future__ import annotations

from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def _vector_arrow_block() -> str:
    start = SRC.index("vel_vec = (")
    end = SRC.index("vel_pos, vel_colors = _arrow_lines_3d(", start)
    return SRC[start:end]


def _method_block(name: str, next_marker: str) -> str:
    start = SRC.index(f"    def {name}(")
    end = SRC.index(next_marker, start)
    return SRC[start:end]


def test_3d_speed_and_accel_arrows_use_solver_truth_channels_with_sign() -> None:
    speed_block = _method_block("_solver_signed_speed_along_road", "    def _solver_external_acceleration_xy(")
    accel_block = _method_block("_solver_external_acceleration_xy", "    # ---------------------------- main update")
    update_block = _method_block("update_frame", "        # ---- Road preview")

    assert "def _solver_signed_speed_along_road(" in speed_block
    assert "def _solver_external_acceleration_xy(" in accel_block
    assert 'get_value("скорость_vx_м_с", 0.0)' in speed_block
    assert 'get_value("ускорение_продольное_ax_м_с2", 0.0)' in accel_block
    assert 'get_value("ускорение_поперечное_ay_м_с2", 0.0)' in accel_block
    arrow_block = _vector_arrow_block()
    assert 'ensure_body_velocity_xy()' not in arrow_block
    assert 'ensure_body_acceleration_xy()' not in arrow_block
    assert 'speed_along_road = self._solver_signed_speed_along_road(' in update_block
    assert 'get_value=_g' in update_block
    assert 'external_ax, external_ay = self._solver_external_acceleration_xy(' in update_block


def test_3d_vector_overlay_ignores_heave_channels_for_user_facing_velocity_and_acceleration_arrows() -> None:
    assert 'np.asarray(R_local[:, 0], dtype=float) * float(speed_along_road * self._vel_scale)' in SRC
    assert 'np.asarray(R_local[:, 0], dtype=float) * float(external_ax * self._accel_scale)' in SRC
    assert '+ np.asarray(R_local[:, 1], dtype=float) * float(external_ay * self._accel_scale)' in SRC
