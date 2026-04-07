# -*- coding: utf-8 -*-
"""Candidate proposal for MOBO (optional BoTorch).

This module is dependency-light by design:
- If BoTorch + PyTorch are available -> use qNEHVI / qLogNEHVI.
- If not -> fall back to random / LHS sampling.

We focus on **2-objective minimization** (obj1, obj2) + an additional
scalar feasibility metric `penalty` (0 = feasible, >0 = violated).

Conventions
-----------
- Training/BO uses maximization, so we convert: Y_max = -Y_min.
- All X_u live in [0,1]^d.

The distributed runners import:
- ProposeOptions (dataclass)
- propose_next(...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .hv_tools import infer_reference_point_max, normalize_for_hv


@dataclass
class ProposeOptions:
    """Options for proposing the next candidate."""

    seed: int = 0
    n_init: int = 16

    # method:
    # - "auto"   : botorch if possible else LHS
    # - "lhs"    : LHS sampling
    # - "random" : uniform random
    # - "botorch": force botorch (fallbacks if not possible)
    method: str = "auto"

    # If False -> never use BoTorch.
    allow_botorch: bool = True

    # torch device preference: "auto" / "cpu" / "cuda"
    device: str = "auto"

    # qNEHVI parameters
    q: int = 1
    num_restarts: int = 10
    raw_samples: int = 256

    # feasibility
    feasible_tol: float = 1e-9
    min_feasible: int = 12

    # hypervolume ref heuristic / normalization
    ref_margin: float = 0.1
    normalize: bool = True
    normalize_quantiles: Tuple[float, float] = (0.1, 0.9)


def _lhs_sample(rng: np.random.Generator, d: int, n: int = 1) -> np.ndarray:
    """Simple Latin Hypercube samples in [0,1]^d."""

    if n <= 0:
        return np.empty((0, d), dtype=float)

    # For each dimension, create n strata and permute
    cut = np.linspace(0.0, 1.0, n + 1)
    u = rng.random((n, d))
    a = cut[:n]
    b = cut[1:]
    rdpoints = u * (b - a)[:, None] + a[:, None]

    H = np.zeros_like(rdpoints)
    for j in range(d):
        order = rng.permutation(n)
        H[:, j] = rdpoints[order, j]
    return H


def _safe_torch_device(device_pref: str):
    """Return torch.device or None if torch is unavailable."""

    try:
        import torch

        if device_pref == "cpu":
            return torch.device("cpu")
        if device_pref == "cuda":
            if torch.cuda.is_available():
                return torch.device("cuda")
            return torch.device("cpu")
        # auto
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    except Exception:
        return None


def _botorch_propose(
    X_u: np.ndarray,
    Y_min: np.ndarray,
    penalty: np.ndarray,
    opt: ProposeOptions,
    bounds: Optional[np.ndarray] = None,
    X_pending: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """BoTorch qNEHVI/qLogNEHVI proposer.

    Returns:
        x_next_u: (d,) in [0,1]
        info: dict with diagnostics
    """

    info: Dict[str, Any] = {"method": "botorch"}

    try:
        import torch

        from botorch.models import SingleTaskGP
        from botorch.models.model_list_gp_regression import ModelListGP
        from botorch.models.transforms.outcome import Standardize
        from botorch.fit import fit_gpytorch_mll
        from botorch.optim import optimize_acqf
        from gpytorch.mlls.sum_marginal_log_likelihood import SumMarginalLogLikelihood

        # acquisition
        # Prefer log-NEHVI if available
        Acq = None
        try:
            from botorch.acquisition.multi_objective.logei import qLogNoisyExpectedHypervolumeImprovement as Acq

            info["acq"] = "qLogNEHVI"
        except Exception:
            from botorch.acquisition.multi_objective.monte_carlo import qNoisyExpectedHypervolumeImprovement as Acq

            info["acq"] = "qNEHVI"

        dev = _safe_torch_device(opt.device)
        if dev is None:
            raise RuntimeError("torch not available")

        # Filter feasible points
        feas_mask = np.isfinite(penalty) & (penalty <= float(opt.feasible_tol))
        n_feas = int(feas_mask.sum())
        info["n_feasible"] = n_feas
        if n_feas < max(2, int(opt.min_feasible)):
            raise RuntimeError(f"not enough feasible points for BO (have {n_feas}, need {opt.min_feasible})")

        X = torch.tensor(X_u[feas_mask], dtype=torch.double, device=dev)
        Y = torch.tensor((-Y_min[feas_mask]), dtype=torch.double, device=dev)  # maximize

        if bounds is None:
            bnds = torch.tensor([[0.0] * X.shape[1], [1.0] * X.shape[1]], dtype=torch.double, device=dev)
        else:
            bnds = torch.tensor(bounds, dtype=torch.double, device=dev)

        # Reference point + (optional) normalization
        ref = infer_reference_point_max(Y.detach().cpu().numpy(), margin=float(opt.ref_margin))
        info["ref_point_max"] = ref.tolist()

        if opt.normalize:
            Y_np = Y.detach().cpu().numpy()
            Y_norm, ref_norm, meta = normalize_for_hv(Y_np, ref, quantiles=opt.normalize_quantiles)
            ref = ref_norm
            info["normalize"] = True
            info["norm_meta"] = meta
            Y = torch.tensor(Y_norm, dtype=torch.double, device=dev)
        else:
            info["normalize"] = False

        # Build independent GPs per objective
        m0 = SingleTaskGP(X, Y[..., [0]], outcome_transform=Standardize(m=1))
        m1 = SingleTaskGP(X, Y[..., [1]], outcome_transform=Standardize(m=1))
        model = ModelListGP(m0, m1)
        model = model.to(dev)

        mll = SumMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)

        acq = Acq(
            model=model,
            X_baseline=X,
            ref_point=torch.tensor(ref, dtype=torch.double, device=dev),
            prune_baseline=True,
        )

        if X_pending is not None and len(X_pending):
            try:
                Xp = torch.tensor(X_pending, dtype=torch.double, device=dev)
                acq.set_X_pending(Xp)
            except Exception:
                pass

        cand, _ = optimize_acqf(
            acq_function=acq,
            bounds=bnds,
            q=int(opt.q),
            num_restarts=int(opt.num_restarts),
            raw_samples=int(opt.raw_samples),
        )

        x_next = cand.detach().cpu().numpy().reshape(-1)
        info["ok"] = True
        return x_next, info

    except Exception as e:
        info["ok"] = False
        info["error"] = str(e)
        raise


def propose_next(
    X_u: np.ndarray,
    Y_min: np.ndarray,
    penalty: np.ndarray,
    opt: ProposeOptions,
    bounds: Optional[np.ndarray] = None,
    X_pending: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Propose the next candidate in normalized space.

    Args:
        X_u: (n,d) previous candidates in [0,1]. May be empty.
        Y_min: (n,2) objectives (minimization). May be empty.
        penalty: (n,) feasibility penalty. May be empty.
        opt: ProposeOptions
        bounds: optional (2,d) bounds in [0,1]
        X_pending: optional (k,d) pending points (for BO)

    Returns:
        x_next_u: (d,) candidate
        info: dict
    """

    info: Dict[str, Any] = {"requested_method": opt.method}

    # Determine dimension
    if X_u is not None and X_u.size:
        d = int(X_u.shape[1])
    else:
        # Deduce from bounds or fail
        if bounds is not None:
            d = int(bounds.shape[1])
        else:
            raise ValueError("Cannot infer dimension d: provide X_u or bounds")

    rng = np.random.default_rng(int(opt.seed))

    method = (opt.method or "auto").strip().lower()
    if method == "auto":
        method = "botorch" if opt.allow_botorch and (X_u.shape[0] if X_u is not None else 0) >= int(opt.n_init) else "lhs"

    # Warm-up always LHS until n_init
    n_obs = int(X_u.shape[0]) if X_u is not None and X_u.size else 0
    if n_obs < int(opt.n_init) and method in {"botorch", "auto"}:
        method = "lhs"

    if method == "random":
        if bounds is None:
            x = rng.random(d)
        else:
            lo = bounds[0]
            hi = bounds[1]
            x = lo + rng.random(d) * (hi - lo)
        info["method"] = "random"
        return x.astype(float), info

    if method == "lhs":
        if bounds is None:
            x = _lhs_sample(rng, d, n=1).reshape(-1)
        else:
            lo = bounds[0]
            hi = bounds[1]
            x0 = _lhs_sample(rng, d, n=1).reshape(-1)
            x = lo + x0 * (hi - lo)
        info["method"] = "lhs"
        return x.astype(float), info

    if method == "botorch":
        if not opt.allow_botorch:
            # fallback
            info["method"] = "lhs"
            x = _lhs_sample(rng, d, n=1).reshape(-1)
            return x.astype(float), info
        # Attempt botorch, fallback to LHS if failed
        try:
            x, binfo = _botorch_propose(X_u=X_u, Y_min=Y_min, penalty=penalty, opt=opt, bounds=bounds, X_pending=X_pending)
            info.update(binfo)
            return x.astype(float), info
        except Exception as e:
            info["method"] = "lhs_fallback"
            info["botorch_error"] = str(e)
            x = _lhs_sample(rng, d, n=1).reshape(-1)
            return x.astype(float), info

    # Unknown method
    info["method"] = "lhs"
    x = _lhs_sample(rng, d, n=1).reshape(-1)
    return x.astype(float), info
