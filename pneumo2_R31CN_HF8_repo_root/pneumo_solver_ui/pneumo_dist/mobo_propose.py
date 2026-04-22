# -*- coding: utf-8 -*-
"""pneumo_dist.mobo_propose

Optional MOBO proposer using BoTorch (qNEHVI / constrained qNEHVI).

This is an optional dependency path:
- If torch/botorch are not installed, the coordinator will fall back to LHS/random.
- If CUDA is available, BoTorch's Monte-Carlo acquisition optimization can benefit from GPU.

We use a *minimization* convention externally:
- Y_min: (n, m) objectives to MINIMIZE
- G_min: (n, k) constraints with feasibility defined as G <= 0

BoTorch assumes *maximization* for objectives, so we negate objectives.
Constraints in BoTorch acquisition functions are expressed as callables returning values where
negative (<=0) implies feasibility.

Reference: BoTorch tutorials on multi-objective BO and constrained MOBO.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .hv_tools import Normalizer, fit_normalizer, infer_reference_point_min


def _has_torch_botorch() -> bool:
    try:
        import torch  # noqa: F401
        import botorch  # noqa: F401
        import gpytorch  # noqa: F401

        return True
    except Exception:
        return False


@dataclass
class ProposeResult:
    X: np.ndarray  # (q,d) in [0,1]
    meta: Dict[str, Any]


def propose_random(*, d: int, q: int, seed: int = 0) -> ProposeResult:
    rng = np.random.default_rng(int(seed))
    X = rng.random((int(q), int(d)))
    return ProposeResult(X=X, meta={"method": "random"})


def propose_heuristic(
    *,
    X_done: np.ndarray,
    Y_min_done: np.ndarray,
    penalty: Optional[np.ndarray],
    q: int,
    seed: int,
    X_pending: Optional[np.ndarray] = None,
    feasible_tol: float = 1e-9,
    pool_size: int = 256,
    explore_weight: float = 0.70,
) -> ProposeResult:
    """Heuristic proposer balancing exploitation and novelty.

    Inputs/outputs are in normalized [0,1] coordinates.
    """
    X_done = np.asarray(X_done, dtype=float)
    if X_done.ndim != 2 or X_done.shape[1] <= 0:
        d = int(X_done.shape[1]) if X_done.ndim == 2 else 1
        return propose_random(d=max(1, d), q=max(1, int(q)), seed=int(seed))

    n, d = X_done.shape
    q_eff = max(1, int(q))
    rng = np.random.default_rng(int(seed))

    Y = np.asarray(Y_min_done, dtype=float)
    pen = np.asarray(penalty, dtype=float).reshape(-1) if penalty is not None else None

    # Robust scalarization: objective sum + penalty excess weight.
    scalar = np.full((n,), np.nan, dtype=float)
    if Y.ndim == 2 and Y.shape[0] == n and Y.shape[1] > 0:
        y_use = np.where(np.isfinite(Y), Y, np.nan)
        scalar = np.nansum(y_use, axis=1)
        valid_rows = np.any(np.isfinite(Y), axis=1)
        scalar = np.where(valid_rows, scalar, np.nan)
    if pen is not None and pen.shape[0] == n:
        tol = float(feasible_tol)
        finite_pen = pen[np.isfinite(pen)]
        if finite_pen.size > 0:
            p_hi = float(np.nanquantile(finite_pen, 0.95))
            if not np.isfinite(p_hi):
                p_hi = float(np.nanmax(finite_pen))
            if not np.isfinite(p_hi):
                p_hi = tol + 1.0
        else:
            p_hi = tol + 1.0
        pen_fill = p_hi + max(1.0, abs(p_hi))
        pen_use = np.where(np.isfinite(pen), pen, pen_fill)

        excess = np.maximum(0.0, pen_use - tol)
        excess_scale = float(np.nanquantile(excess, 0.9)) if np.any(np.isfinite(excess)) else 0.0
        if not np.isfinite(excess_scale) or excess_scale <= 1e-12:
            excess_scale = 1.0
        scalar = np.where(np.isfinite(scalar), scalar, 0.0) + 5.0 * (excess / excess_scale)

    finite_mask = np.isfinite(scalar)
    if np.any(finite_mask):
        idx_f = np.where(finite_mask)[0]
        rank = np.argsort(scalar[idx_f])
        elite_k = max(3, int(math.sqrt(max(1, n))))
        elite_idx = idx_f[rank[:elite_k]]
        elite = X_done[elite_idx]
    else:
        elite = X_done

    center = np.nanmedian(elite, axis=0)
    center = np.where(np.isfinite(center), center, 0.5)
    center = np.clip(center, 0.0, 1.0)

    spread = np.nanstd(elite, axis=0)
    spread = np.where(np.isfinite(spread), spread, 0.15)
    spread = np.clip(spread, 0.05, 0.35)

    occupied_parts: List[np.ndarray] = [X_done]
    if X_pending is not None:
        xp = np.asarray(X_pending, dtype=float)
        if xp.ndim == 2 and xp.shape[1] == d and xp.shape[0] > 0:
            occupied_parts.append(xp)
    occupied = np.vstack(occupied_parts) if occupied_parts else np.empty((0, d), dtype=float)
    if occupied.shape[0] > 1024:
        # Keep distance cost bounded on long runs.
        occupied = occupied[-1024:]

    selected: List[np.ndarray] = []
    explore = float(np.clip(explore_weight, 0.0, 1.0))
    pool_n = max(64, int(pool_size))
    local_n = max(32, pool_n // 2)
    global_n = max(32, pool_n - local_n)

    for _ in range(q_eff):
        local = center + rng.normal(loc=0.0, scale=spread * 0.65, size=(local_n, d))
        local = np.clip(local, 0.0, 1.0)
        global_pool = rng.random((global_n, d))
        pool = np.vstack([local, global_pool])

        if occupied.shape[0] > 0:
            diff = pool[:, None, :] - occupied[None, :, :]
            novelty = np.sqrt(np.sum(diff * diff, axis=2)).min(axis=1)
        else:
            novelty = np.ones((pool.shape[0],), dtype=float)

        exploit = -np.linalg.norm(pool - center.reshape(1, -1), axis=1) / (math.sqrt(d) + 1e-12)
        score = (explore * novelty) + ((1.0 - explore) * exploit)
        score = score + (1e-9 * rng.standard_normal(score.shape[0]))

        best_idx = int(np.argmax(score))
        x_best = np.asarray(pool[best_idx], dtype=float).reshape(1, -1)
        selected.append(x_best.reshape(-1))
        occupied = np.vstack([occupied, x_best]) if occupied.size else x_best

    X_new = np.vstack(selected).astype(float, copy=False)
    X_new = np.clip(X_new, 0.0, 1.0)
    meta: Dict[str, Any] = {
        "method": "heuristic",
        "n_train": int(n),
        "n_pending": int(0 if X_pending is None else np.asarray(X_pending).shape[0]),
        "center": [float(v) for v in center.tolist()],
        "explore_weight": float(explore),
    }
    return ProposeResult(X=X_new, meta=meta)


def propose_qnehvi(
    *,
    X_done: np.ndarray,
    Y_min_done: np.ndarray,
    G_min_done: Optional[np.ndarray],
    q: int,
    seed: int,
    X_pending: Optional[np.ndarray] = None,
    device: str = "auto",
    normalize_objectives: bool = True,
    ref_margin: float = 0.10,
    num_restarts: int = 10,
    raw_samples: int = 512,
    maxiter: int = 200,
) -> ProposeResult:
    """Constrained qNEHVI proposer.

    Returns X in [0,1]^d.

    Notes:
    - If constraints are provided, we append them to the model outputs and pass a constraint callable.
    - For numerical stability we typically normalize objectives to a comparable scale.
    """

    if not _has_torch_botorch():
        return propose_random(d=int(X_done.shape[-1]), q=q, seed=seed)

    import torch
    from botorch.acquisition.multi_objective.monte_carlo import qNoisyExpectedHypervolumeImprovement
    from botorch.acquisition.multi_objective.objective import IdentityMCMultiOutputObjective
    from botorch.fit import fit_gpytorch_mll
    from botorch.models.gp_regression import SingleTaskGP
    from botorch.models.model_list_gp_regression import ModelListGP
    from botorch.optim.optimize import optimize_acqf
    from gpytorch.mlls.sum_marginal_log_likelihood import SumMarginalLogLikelihood

    X_done = np.asarray(X_done, dtype=float)
    Y_min_done = np.asarray(Y_min_done, dtype=float)
    if G_min_done is not None:
        G_min_done = np.asarray(G_min_done, dtype=float)

    n, d = X_done.shape
    m = Y_min_done.shape[1]
    k = 0 if G_min_done is None else G_min_done.shape[1]

    # Not enough data -> random
    if n < max(2 * (d + 1), 8):
        return propose_random(d=d, q=q, seed=seed)

    # Normalization in minimization space
    norm: Optional[Normalizer] = None
    if normalize_objectives:
        norm = fit_normalizer(Y_min_done, method="quantile")
        Y_min_use = norm.transform(Y_min_done)
    else:
        Y_min_use = Y_min_done

    # BoTorch maximizes
    Y_obj_max = -Y_min_use

    # Constraints: already <=0 feasible, keep as is.
    if k > 0 and G_min_done is not None:
        Y_train = np.concatenate([Y_obj_max, G_min_done], axis=1)
    else:
        Y_train = Y_obj_max

    # Device selection
    if device == "auto":
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = torch.device(device)

    tkwargs = {"dtype": torch.double, "device": dev}

    train_x = torch.tensor(X_done, **tkwargs)
    train_y = torch.tensor(Y_train, **tkwargs)

    models = []
    for i in range(train_y.shape[-1]):
        models.append(SingleTaskGP(train_x, train_y[..., i : i + 1]))
    model = ModelListGP(*models)
    mll = SumMarginalLogLikelihood(model.likelihood, model)
    fit_gpytorch_mll(mll)

    # Reference point in minimization -> convert to maximization
    ref_min = infer_reference_point_min(Y_min_use, margin=ref_margin)
    ref_max = (-ref_min).tolist()

    # Setup qNEHVI
    # outcomes=[0..m-1] are objectives, last k are constraints
    acq = qNoisyExpectedHypervolumeImprovement(
        model=model,
        ref_point=ref_max,
        X_baseline=train_x,
        prune_baseline=True,
        objective=IdentityMCMultiOutputObjective(outcomes=list(range(m))),
        constraints=([lambda Z: Z[..., -j] for j in range(1, k + 1)][::-1] if k > 0 else None),
    )

    # Pending points
    if X_pending is not None and hasattr(acq, "set_X_pending"):
        Xp = torch.tensor(np.asarray(X_pending, dtype=float), **tkwargs)
        acq.set_X_pending(Xp)

    bounds = torch.zeros(2, d, **tkwargs)
    bounds[1] = 1.0

    torch.manual_seed(int(seed))

    candidates, _ = optimize_acqf(
        acq_function=acq,
        bounds=bounds,
        q=int(q),
        num_restarts=int(num_restarts),
        raw_samples=int(raw_samples),
        options={"batch_limit": 5, "maxiter": int(maxiter)},
        sequential=True,
    )

    X_new = candidates.detach().cpu().numpy()
    X_new = np.clip(X_new, 0.0, 1.0)

    meta: Dict[str, Any] = {
        "method": "qNEHVI",
        "device": str(dev),
        "normalize_objectives": bool(normalize_objectives),
        "ref_min": ref_min.tolist(),
        "ref_max": ref_max,
        "m": int(m),
        "k": int(k),
        "n_train": int(n),
    }
    return ProposeResult(X=X_new, meta=meta)


# -----------------------------------------------------------------------------
# Backward-compat (older distributed tools expect ProposeOptions + propose_next)
# -----------------------------------------------------------------------------

@dataclass
class ProposeOptions:
    method: str = "auto"  # auto|qnehvi|heuristic|random
    allow_botorch: bool = True
    device: str = "auto"
    q: int = 1
    num_restarts: int = 8
    raw_samples: int = 128
    seed: int = 0
    feasible_tol: float = 1e-9
    min_feasible: int = 8
    use_constraint_model: bool = True
    n_init: int = 16
    heuristic_pool_size: int = 256
    heuristic_explore: float = 0.70


def propose_next(
    X_u: Optional[np.ndarray],
    Y_min: Optional[np.ndarray],
    penalty: Optional[np.ndarray],
    opt: ProposeOptions,
    bounds_u: np.ndarray,
    X_pending: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Propose next candidate(s) in normalized space U.

    Returns:
        (X_new, meta)
        where X_new has shape (q, d) (q from options).
    """

    method = (opt.method or "auto").strip().lower()
    d = int(bounds_u.shape[1]) if bounds_u is not None and getattr(bounds_u, "ndim", 0) == 2 else None

    lo = np.asarray(bounds_u[0], dtype=float) if bounds_u is not None and getattr(bounds_u, "ndim", 0) == 2 else None
    hi = np.asarray(bounds_u[1], dtype=float) if bounds_u is not None and getattr(bounds_u, "ndim", 0) == 2 else None
    if lo is not None and hi is not None:
        span = np.where(np.abs(hi - lo) > 1e-12, hi - lo, 1.0)
        need_scale = bool(np.any(lo != 0.0) or np.any(hi != 1.0))
    else:
        span = None
        need_scale = False

    def _to_unit(X: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if X is None:
            return None
        arr = np.asarray(X, dtype=float)
        if not need_scale or lo is None or span is None:
            return arr
        return np.clip((arr - lo.reshape(1, -1)) / span.reshape(1, -1), 0.0, 1.0)

    def _from_unit(X: np.ndarray) -> np.ndarray:
        arr = np.asarray(X, dtype=float)
        if not need_scale or lo is None or span is None:
            return arr
        return lo.reshape(1, -1) + (span.reshape(1, -1) * arr)

    def _random_fallback(reason: str, err: Optional[Exception] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        dd = int(d or 0)
        if dd <= 0:
            try:
                x_arr = np.asarray(X_u, dtype=float)
                if x_arr.ndim == 2 and x_arr.shape[1] > 0:
                    dd = int(x_arr.shape[1])
                elif x_arr.ndim == 1 and x_arr.size > 0:
                    dd = int(x_arr.size)
                else:
                    dd = 1
            except Exception:
                dd = 1
        dd = max(1, int(dd))
        rr = propose_random(d=dd, q=max(1, int(opt.q)), seed=int(opt.seed))
        X = _from_unit(rr.X)
        meta = dict(rr.meta)
        meta.update({"method": "random", "fallback_reason": reason})
        if err is not None:
            meta["fallback_error"] = f"{type(err).__name__}: {err}"
        return X, meta

    def _heuristic_fallback(reason: str, err: Optional[Exception] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        if X_u is None or Y_min is None:
            return _random_fallback(reason, err)
        try:
            X_unit = _to_unit(X_u)
            Xp_unit = _to_unit(X_pending) if X_pending is not None else None
            if X_unit is None:
                return _random_fallback(reason, err)
            res = propose_heuristic(
                X_done=np.asarray(X_unit, dtype=float),
                Y_min_done=np.asarray(Y_min, dtype=float),
                penalty=np.asarray(penalty, dtype=float).reshape(-1) if penalty is not None else None,
                q=max(1, int(opt.q)),
                seed=int(opt.seed),
                X_pending=np.asarray(Xp_unit, dtype=float) if Xp_unit is not None else None,
                feasible_tol=float(opt.feasible_tol),
                pool_size=int(getattr(opt, "heuristic_pool_size", 256) or 256),
                explore_weight=float(getattr(opt, "heuristic_explore", 0.70)),
            )
            X_new = _from_unit(res.X)
            meta = dict(res.meta)
            meta["fallback_reason"] = reason
            if err is not None:
                meta["fallback_error"] = f"{type(err).__name__}: {err}"
            return X_new, meta
        except Exception as e:
            return _random_fallback(f"{reason}_heuristic_failed", e)

    # Not enough history -> random
    if X_u is None or Y_min is None:
        return _random_fallback("no_history")

    X_u = np.asarray(X_u, dtype=float)
    Y_min = np.asarray(Y_min, dtype=float)
    if X_u.ndim != 2 or Y_min.ndim != 2 or X_u.shape[0] != Y_min.shape[0]:
        return _random_fallback("bad_history_shape")

    if method in {"random", "rand"}:
        return _random_fallback("forced_random")

    if method in {"heuristic", "heur"}:
        return _heuristic_fallback("forced_heuristic")

    if X_u.shape[0] < max(2, int(opt.n_init)):
        return _heuristic_fallback("not_enough_points")

    if method in {"auto", "qnehvi", "nehvi", "botorch"} and (not bool(opt.allow_botorch)):
        return _heuristic_fallback("botorch_disabled")

    # Try qNEHVI if allowed
    if method in {"auto", "qnehvi", "nehvi", "botorch"} and bool(opt.allow_botorch):
        try:
            G = None
            if penalty is not None and bool(opt.use_constraint_model):
                pen = np.asarray(penalty, dtype=float).reshape(-1)
                n_feasible = int((pen <= float(opt.feasible_tol)).sum())
                if n_feasible < int(opt.min_feasible):
                    return _heuristic_fallback("not_enough_feasible")
                G = pen.reshape(-1, 1)

            res = propose_qnehvi(
                X_done=np.asarray(_to_unit(X_u), dtype=float),
                Y_min_done=Y_min,
                G_min_done=G,
                q=max(1, int(opt.q)),
                seed=int(opt.seed),
                X_pending=np.asarray(_to_unit(X_pending), dtype=float) if X_pending is not None else None,
                device=str(opt.device),
                num_restarts=int(opt.num_restarts),
                raw_samples=int(opt.raw_samples),
            )

            X_new = _from_unit(res.X)

            return X_new, {**res.meta, "method": "qnehvi"}
        except Exception as e:
            return _heuristic_fallback("qnehvi_failed", e)

    # Fallback
    return _heuristic_fallback("unsupported_method")
