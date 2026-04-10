from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.playback_sampling import lerp_wrapped_angle_value


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_wrapped_angle_lerp_uses_shortest_arc_across_pi_boundary() -> None:
    series = np.asarray([math.pi - 0.04, -math.pi + 0.04], dtype=float)
    mid = lerp_wrapped_angle_value(series, i0=0, i1=1, alpha=0.5)
    assert abs(mid) > 3.0
    assert abs(abs(mid) - math.pi) <= 0.05


def test_wrapped_angle_lerp_prefers_finite_endpoint_when_other_is_invalid() -> None:
    series = np.asarray([math.pi - 0.2, float("nan")], dtype=float)
    out = lerp_wrapped_angle_value(series, i0=0, i1=1, alpha=0.5, default=0.0)
    assert abs(out - (math.pi - 0.2)) <= 1e-12


def test_animator_uses_angle_aware_sampling_for_yaw_and_attitude() -> None:
    assert "lerp_wrapped_angle_value as _lerp_wrapped_angle_value" in APP
    assert "def _sample_angle_series_local(" in APP
    assert 'yaw0 = _ga("yaw_рад", 0.0)' in APP
    assert 'roll = _ga("крен_phi_рад", 0.0)' in APP
    assert 'pitch = _ga("тангаж_theta_рад", 0.0)' in APP
    assert 'yaw = _sample_angle_series_local(yaw_series, i0=sample_i0, i1=sample_i1, alpha=alpha, default=0.0)' in APP
    assert 'yaw = _sample_angle_series_local(summary["yaw"], i0=int(sample_i0), i1=int(sample_i1), alpha=float(alpha), default=0.0)' in APP
