import numpy as np
import pytest

from pneumo_solver_ui.time_grid import build_time_grid


def test_build_time_grid_floor_keeps_requested_step_and_no_overshoot() -> None:
    dt = 0.2
    t = build_time_grid(dt=dt, t_end=1.0, t0=0.0, mode="floor")
    assert np.all(np.isfinite(t))
    assert t[0] == pytest.approx(0.0)
    assert t[-1] <= 1.0 + 1e-15
    assert np.all(np.diff(t) == pytest.approx(dt))


def test_build_time_grid_ceil_reaches_or_exceeds_horizon() -> None:
    dt = 0.3
    t = build_time_grid(dt=dt, t_end=1.0, t0=0.0, mode="ceil")
    assert np.all(np.isfinite(t))
    assert t[0] == pytest.approx(0.0)
    assert t[-1] >= 1.0 - 1e-15
    assert np.all(np.diff(t) == pytest.approx(dt))


def test_build_time_grid_returns_single_point_when_t_end_not_after_t0() -> None:
    t = build_time_grid(dt=1e-3, t_end=0.0, t0=0.0, mode="floor")
    assert t.shape == (1,)
    assert t[0] == pytest.approx(0.0)


@pytest.mark.parametrize("bad_dt", [float("nan"), float("inf"), -float("inf"), 0.0, -1.0])
def test_build_time_grid_rejects_nonfinite_or_nonpositive_dt(bad_dt) -> None:
    with pytest.raises(ValueError, match="dt must be finite and > 0"):
        build_time_grid(dt=bad_dt, t_end=1.0, t0=0.0, mode="floor")


@pytest.mark.parametrize("bad_t_end", [float("nan"), float("inf"), -float("inf")])
def test_build_time_grid_rejects_nonfinite_t_end(bad_t_end) -> None:
    with pytest.raises(ValueError, match="t_end must be finite"):
        build_time_grid(dt=1e-3, t_end=bad_t_end, t0=0.0, mode="floor")


@pytest.mark.parametrize("bad_t0", [float("nan"), float("inf"), -float("inf")])
def test_build_time_grid_rejects_nonfinite_t0(bad_t0) -> None:
    with pytest.raises(ValueError, match="t0 must be finite"):
        build_time_grid(dt=1e-3, t_end=1.0, t0=bad_t0, mode="floor")
