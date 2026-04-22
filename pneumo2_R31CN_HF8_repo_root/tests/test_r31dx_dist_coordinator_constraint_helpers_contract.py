from __future__ import annotations

import numpy as np

from pneumo_solver_ui.tools import dist_opt_coordinator as coord


def test_r31dx_count_feasible_trials_handles_none_empty_and_numpy_arrays() -> None:
    assert coord._count_feasible_trials(None) == 0
    assert coord._count_feasible_trials([]) == 0

    arr = np.asarray([[-0.10, 0.0], [0.20, -0.30], [-0.01, -0.02]], dtype=float)
    assert coord._count_feasible_trials(arr) == 2


def test_r31dx_count_feasible_trials_is_robust_to_invalid_rows() -> None:
    g_rows = [
        [-0.10, 0.0],   # feasible
        [0.20, -0.10],  # infeasible
        [-0.30],        # feasible
        [np.nan, -0.1], # non-finite -> treated as infeasible
        "bad_row",      # unparsable -> treated as infeasible
        [np.inf, -0.2], # non-finite -> treated as infeasible
    ]
    assert coord._count_feasible_trials(g_rows) == 2


def test_r31dx_heuristic_penalty_from_constraints_handles_none_empty_and_scalars() -> None:
    assert coord._heuristic_penalty_from_constraints(None) is None
    assert coord._heuristic_penalty_from_constraints([]) is None

    out = coord._heuristic_penalty_from_constraints([-0.25, 0.30])
    np.testing.assert_allclose(out, np.asarray([-0.25, 0.30], dtype=float), atol=0.0, rtol=0.0)


def test_r31dx_heuristic_penalty_from_constraints_returns_rowwise_max_with_nan_for_invalid() -> None:
    g_rows = [
        [-0.10, 0.00],
        [0.20, -0.10],
        [-0.30],
        [np.nan, -0.1],
        "bad_row",
        [np.inf, -0.2],
    ]
    out = coord._heuristic_penalty_from_constraints(g_rows)
    expected = np.asarray([0.0, 0.2, -0.3, np.nan, np.nan, np.nan], dtype=float)
    np.testing.assert_allclose(out, expected, atol=0.0, rtol=0.0, equal_nan=True)
