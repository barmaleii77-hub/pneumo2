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
    method: str = "auto"  # auto|qnehvi|random
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

    def _random_fallback(reason: str, err: Optional[Exception] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        dd = d or (int(np.asarray(X_u).shape[1]) if X_u is not None else 1)
        rr = propose_random(d=dd, q=max(1, int(opt.q)), seed=int(opt.seed))
        X = rr.X
        # scale to bounds_u if not [0,1]
        try:
            lo = np.asarray(bounds_u[0], dtype=float)
            hi = np.asarray(bounds_u[1], dtype=float)
            if np.any(lo != 0.0) or np.any(hi != 1.0):
                X = lo + (hi - lo) * X
        except Exception:
            pass
        meta = dict(rr.meta)
        meta.update({"method": "random", "fallback_reason": reason})
        if err is not None:
            meta["fallback_error"] = f"{type(err).__name__}: {err}"
        return X, meta

    # Not enough history -> random
    if X_u is None or Y_min is None:
        return _random_fallback("no_history")

    X_u = np.asarray(X_u, dtype=float)
    Y_min = np.asarray(Y_min, dtype=float)
    if X_u.ndim != 2 or Y_min.ndim != 2 or X_u.shape[0] != Y_min.shape[0]:
        return _random_fallback("bad_history_shape")

    if X_u.shape[0] < max(2, int(opt.n_init)):
        return _random_fallback("not_enough_points")

    if method in {"random", "rand"}:
        return _random_fallback("forced_random")

    # Try qNEHVI if allowed
    if method in {"auto", "qnehvi", "nehvi", "botorch"} and bool(opt.allow_botorch):
        try:
            G = None
            if penalty is not None and bool(opt.use_constraint_model):
                pen = np.asarray(penalty, dtype=float).reshape(-1)
                n_feasible = int((pen <= float(opt.feasible_tol)).sum())
                if n_feasible < int(opt.min_feasible):
                    return _random_fallback("not_enough_feasible")
                G = pen.reshape(-1, 1)

            res = propose_qnehvi(
                X_done=X_u,
                Y_min_done=Y_min,
                G_min_done=G,
                q=max(1, int(opt.q)),
                seed=int(opt.seed),
                X_pending=np.asarray(X_pending, dtype=float) if X_pending is not None else None,
                device=str(opt.device),
                num_restarts=int(opt.num_restarts),
                raw_samples=int(opt.raw_samples),
            )

            X_new = res.X
            # scale to bounds_u if not [0,1]
            try:
                lo = np.asarray(bounds_u[0], dtype=float)
                hi = np.asarray(bounds_u[1], dtype=float)
                if np.any(lo != 0.0) or np.any(hi != 1.0):
                    X_new = lo + (hi - lo) * X_new
            except Exception:
                pass

            return X_new, {**res.meta, "method": "qnehvi"}
        except Exception as e:
            return _random_fallback("qnehvi_failed", e)

    # Fallback
    return _random_fallback("unsupported_method")
