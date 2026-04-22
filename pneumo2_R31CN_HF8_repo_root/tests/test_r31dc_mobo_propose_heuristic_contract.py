from __future__ import annotations

import numpy as np

from pneumo_solver_ui.pneumo_dist.mobo_propose import ProposeOptions, propose_next


def _min_dist_to_set(X: np.ndarray, S: np.ndarray) -> np.ndarray:
    diff = X[:, None, :] - S[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2)).min(axis=1)


def test_r31dc_forced_heuristic_returns_novel_points() -> None:
    X_u = np.asarray(
        [
            [0.10, 0.10],
            [0.15, 0.12],
            [0.80, 0.85],
            [0.90, 0.90],
        ],
        dtype=float,
    )
    Y_min = np.asarray(
        [
            [1.0, 1.1],
            [0.9, 1.0],
            [2.5, 2.2],
            [2.8, 2.7],
        ],
        dtype=float,
    )
    penalty = np.asarray([0.0, 0.0, 0.6, 0.8], dtype=float)
    X_pending = np.asarray([[0.11, 0.11]], dtype=float)
    bounds_u = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    opt = ProposeOptions(
        method="heuristic",
        allow_botorch=False,
        q=2,
        seed=42,
        n_init=1,
        min_feasible=1,
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=X_pending)

    assert X_new.shape == (2, 2)
    assert np.all(np.isfinite(X_new))
    assert np.all((X_new >= 0.0) & (X_new <= 1.0))
    assert str(meta.get("method")) == "heuristic"
    assert str(meta.get("fallback_reason")) == "forced_heuristic"

    occupied = np.vstack([X_u, X_pending])
    dist = _min_dist_to_set(np.asarray(X_new, dtype=float), occupied)
    assert np.all(dist > 1e-6)


def test_r31dc_auto_without_botorch_prefers_heuristic_fallback() -> None:
    X_u = np.asarray([[0.2, 0.2], [0.3, 0.35], [0.7, 0.75]], dtype=float)
    Y_min = np.asarray([[1.2, 1.0], [1.0, 0.95], [2.0, 2.2]], dtype=float)
    penalty = np.asarray([0.0, 0.05, 0.8], dtype=float)
    bounds_u = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    opt = ProposeOptions(
        method="auto",
        allow_botorch=False,
        q=1,
        seed=7,
        n_init=2,
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=None)

    assert X_new.shape == (1, 2)
    assert str(meta.get("method")) == "heuristic"
    assert str(meta.get("fallback_reason")) == "botorch_disabled"


def test_r31dc_not_enough_feasible_uses_heuristic() -> None:
    X_u = np.asarray([[0.2, 0.2], [0.25, 0.3], [0.3, 0.35], [0.9, 0.9]], dtype=float)
    Y_min = np.asarray([[1.0, 1.1], [0.95, 1.0], [0.9, 1.2], [3.0, 2.5]], dtype=float)
    penalty = np.asarray([1.0, 1.2, 0.9, 2.0], dtype=float)  # none feasible for tol=1e-9
    bounds_u = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    opt = ProposeOptions(
        method="qnehvi",
        allow_botorch=True,
        use_constraint_model=True,
        min_feasible=2,
        q=1,
        seed=9,
        n_init=2,
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=None)

    assert X_new.shape == (1, 2)
    assert str(meta.get("method")) == "heuristic"
    assert str(meta.get("fallback_reason")) == "not_enough_feasible"


def test_r31dc_heuristic_respects_non_unit_bounds() -> None:
    X_u = np.asarray([[10.0, 20.0], [11.0, 21.5], [15.0, 28.0]], dtype=float)
    Y_min = np.asarray([[1.0, 1.2], [0.95, 1.1], [2.0, 2.5]], dtype=float)
    penalty = np.asarray([0.0, 0.0, 0.7], dtype=float)
    bounds_u = np.asarray([[10.0, 20.0], [20.0, 40.0]], dtype=float)

    opt = ProposeOptions(
        method="heuristic",
        allow_botorch=False,
        q=1,
        seed=13,
        n_init=1,
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=None)

    assert X_new.shape == (1, 2)
    assert str(meta.get("method")) == "heuristic"
    assert np.all(X_new >= bounds_u[0] - 1e-12)
    assert np.all(X_new <= bounds_u[1] + 1e-12)


def test_r31dc_heuristic_handles_nonfinite_penalty_values() -> None:
    X_u = np.asarray(
        [
            [0.10, 0.10],
            [0.20, 0.25],
            [0.60, 0.70],
            [0.85, 0.90],
        ],
        dtype=float,
    )
    Y_min = np.asarray(
        [
            [1.0, 1.1],
            [0.95, 1.0],
            [2.0, 2.2],
            [2.8, 2.9],
        ],
        dtype=float,
    )
    penalty = np.asarray([0.0, np.nan, np.inf, 0.3], dtype=float)
    bounds_u = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    opt = ProposeOptions(
        method="heuristic",
        allow_botorch=False,
        q=2,
        seed=123,
        n_init=1,
        min_feasible=1,
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=None)

    assert X_new.shape == (2, 2)
    assert np.all(np.isfinite(X_new))
    assert np.all((X_new >= 0.0) & (X_new <= 1.0))
    assert str(meta.get("method")) == "heuristic"
    assert str(meta.get("fallback_reason")) == "forced_heuristic"


def test_r31dc_heuristic_ignores_rows_with_all_nonfinite_objectives() -> None:
    X_u = np.asarray(
        [
            [0.10, 0.10],  # all-nonfinite objectives (must not dominate exploit center)
            [0.85, 0.86],
            [0.90, 0.88],
            [0.95, 0.92],
        ],
        dtype=float,
    )
    Y_min = np.asarray(
        [
            [np.nan, np.inf],
            [1.0, 1.1],
            [1.1, 1.2],
            [1.2, 1.3],
        ],
        dtype=float,
    )
    penalty = np.asarray([0.0, 0.0, 0.0, 0.0], dtype=float)
    bounds_u = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    opt = ProposeOptions(
        method="heuristic",
        allow_botorch=False,
        q=1,
        seed=321,
        n_init=1,
        min_feasible=1,
        heuristic_pool_size=512,
        heuristic_explore=0.0,  # pure exploit around elite center
    )
    X_new, meta = propose_next(X_u, Y_min, penalty, opt, bounds_u=bounds_u, X_pending=None)

    assert X_new.shape == (1, 2)
    assert np.all(np.isfinite(X_new))
    assert str(meta.get("method")) == "heuristic"
    assert str(meta.get("fallback_reason")) == "forced_heuristic"
    # Candidate should stay near finite-objective cluster, not near the [0.1,0.1] nonfinite row.
    assert float(X_new[0, 0]) > 0.75
    assert float(X_new[0, 1]) > 0.75
