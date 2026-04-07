from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import clamp_window_to_interpolation_support

APP = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_clamp_window_to_interpolation_support_uses_common_finite_bounds() -> None:
    s0 = np.linspace(0.0, 10.0, 11)
    s1 = np.linspace(1.0, 9.0, 9)
    s2 = np.linspace(-2.0, 8.0, 11)
    lo, hi = clamp_window_to_interpolation_support(
        request_start_m=-5.0,
        request_end_m=12.0,
        support_axes=(s0, s1, s2),
    )
    assert lo == 1.0
    assert hi == 8.0


def test_clamped_window_prevents_flat_endpoint_repeats_from_np_interp() -> None:
    s = np.linspace(0.0, 10.0, 11)
    x = np.asarray(s, dtype=float)
    lo, hi = clamp_window_to_interpolation_support(
        request_start_m=-3.0,
        request_end_m=4.0,
        support_axes=(s, s, s, s),
    )
    s_nodes = np.linspace(lo, hi, 40, dtype=float)
    x_nodes = np.interp(s_nodes, s, x)
    assert np.all(np.diff(x_nodes) > 0.0)


def test_car3d_playback_perf_fix_is_wired_in_source() -> None:
    assert "def set_playback_state(self, playing: bool) -> None:" in APP
    assert "def set_playback_perf_mode(self, enabled: bool) -> None:" in APP
    assert "self.car3d.set_playback_state(bool(playing))" in APP
    assert "self.car3d.set_playback_perf_mode(enabled)" in APP
    assert "_clamp_window_to_interpolation_support(" in APP
