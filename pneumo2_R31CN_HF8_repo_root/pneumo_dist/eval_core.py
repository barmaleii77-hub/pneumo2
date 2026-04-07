# -*- coding: utf-8 -*-
"""pneumo_dist.eval_core

Reusable evaluation core for distributed optimization.

This module loads:
- a selected model python file (e.g. model_pneumo_v8_energy_audit_vacuum.py)
- the evaluation logic from opt_worker_v3_margins_energy.py

and exposes a light API:
- map X in [0,1]^d -> params dict
- evaluate a candidate -> (objectives y, constraints g, full metrics row)

The core reuses existing evaluation code as the "source of truth".
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_module_from_path(module_name: str, path: str):
    """Load a Python module from a file path without importing_toggle side effects."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _safe_float(x: Any, default: float = float("inf")) -> float:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
        return default
    except Exception:
        return default


@dataclass
class EvaluatorConfig:
    # Integration timestep and horizons
    dt: float = 0.003
    t_end_inertia: float = 1.2
    t_end_micro: float = 1.6
    t_end_short: float = 1.2
    t_step: float = 0.4

    # "time to settle" metric parameters (see opt_worker)
    settle_band_min_deg: float = 0.5
    settle_band_ratio: float = 0.20

    # Default speed for some road tests
    speed_m_s_default: float = 10.0

    # Objectives (minimization)
    objective_keys: Tuple[str, ...] = (
        "цель1_устойчивость_инерция__с",
        "цель2_комфорт__RMS_ускор_м_с2",
        "метрика_энергия_дроссели_микро_Дж",
    )

    # Constraints (<= 0 feasible)
    penalty_key: str = "штраф_физичности_сумма"
    penalty_tol: float = 0.0


class EvaluatorCore:
    """Loads model + worker and evaluates candidates."""

    def __init__(
        self,
        *,
        model_path: str,
        worker_path: str,
        base_json: Optional[str] = None,
        ranges_json: Optional[str] = None,
        suite_json: Optional[str] = None,
        cfg: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.model_path = str(model_path)
        self.worker_path = str(worker_path)
        self.base_json = str(base_json) if base_json else None
        self.ranges_json = str(ranges_json) if ranges_json else None
        self.suite_json = str(suite_json) if suite_json else None

        # Load modules
        self.worker = _load_module_from_path("pneumo_worker_eval", self.worker_path)
        self.model = _load_module_from_path("pneumo_model_eval", self.model_path)

        P_ATM = float(getattr(self.model, "P_ATM", 101325.0))

        # Base + ranges (as in worker)
        base, ranges = self.worker.make_base_and_ranges(P_ATM)

        # Overrides from JSON (UI usually passes these)
        if self.base_json and os.path.exists(self.base_json):
            try:
                base_override = _load_json(self.base_json)
                if isinstance(base_override, dict):
                    base.update(base_override)
            except Exception:
                pass

        if self.ranges_json and os.path.exists(self.ranges_json):
            try:
                ranges_override = _load_json(self.ranges_json)
                if isinstance(ranges_override, dict):
                    for k, v in ranges_override.items():
                        if isinstance(v, (list, tuple)) and len(v) == 2:
                            ranges[str(k)] = (float(v[0]), float(v[1]))
            except Exception:
                pass

        self.base: Dict[str, Any] = dict(base)
        self.ranges: Dict[str, Tuple[float, float]] = {str(k): (float(v[0]), float(v[1])) for k, v in ranges.items()}
        self.names: List[str] = list(self.ranges.keys())

        lo = []
        hi = []
        for nm in self.names:
            a, b = self.ranges[nm]
            lo.append(float(a))
            hi.append(float(b))
        self.bounds_lo = np.asarray(lo, dtype=float)
        self.bounds_hi = np.asarray(hi, dtype=float)

        # Config
        cfg0 = EvaluatorConfig()
        if cfg and isinstance(cfg, dict):
            # allow overriding some cfg values
            for k, v in cfg.items():
                if hasattr(cfg0, k):
                    try:
                        setattr(cfg0, k, v)
                    except Exception:
                        pass

        self.cfg0 = cfg0

        suite = None
        if self.suite_json and os.path.exists(self.suite_json):
            try:
                suite = _load_json(self.suite_json)
            except Exception:
                suite = None

        # Build cfg dict expected by worker
        self.cfg: Dict[str, Any] = {
            "dt": float(cfg0.dt),
            "t_end_inertia": float(cfg0.t_end_inertia),
            "t_end_micro": float(cfg0.t_end_micro),
            "t_end_short": float(cfg0.t_end_short),
            "t_step": float(cfg0.t_step),
            "suite": suite,
            "settle_band_min_deg": float(cfg0.settle_band_min_deg),
            "settle_band_ratio": float(cfg0.settle_band_ratio),
        }
        # Geometry defaults for road tests
        self.cfg.setdefault("колея", float(self.base.get("колея", 1.2)))
        self.cfg.setdefault("база", float(self.base.get("база", 2.3)))
        self.cfg.setdefault("скорость_м_с_по_умолчанию", float(cfg0.speed_m_s_default))

    # ---- mapping ----

    def dim(self) -> int:
        return int(len(self.names))

    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.bounds_lo.copy(), self.bounds_hi.copy()

    def u_to_params(self, x_u: Sequence[float]) -> Dict[str, Any]:
        x = np.asarray(list(x_u), dtype=float)
        if x.shape != (self.dim(),):
            raise ValueError(f"x_u must have shape ({self.dim()},), got {x.shape}")
        x = np.clip(x, 0.0, 1.0)
        p = dict(self.base)
        span = self.bounds_hi - self.bounds_lo
        vals = self.bounds_lo + x * span
        for nm, v in zip(self.names, vals.tolist()):
            p[nm] = float(v)
        return p

    # ---- evaluation ----

    def evaluate(self, *, trial_id: str, x_u: Sequence[float]) -> Tuple[List[float], List[float], Dict[str, Any]]:
        """Return (y objectives, g constraints, metrics_row)."""
        params = self.u_to_params(x_u)

        # worker wants int id
        try:
            idx_int = int(trial_id[:8], 16)
        except Exception:
            idx_int = abs(hash(trial_id)) % 2_000_000_000

        row = self.worker.eval_candidate(self.model, int(idx_int), params, self.cfg)
        if not isinstance(row, dict):
            raise RuntimeError("eval_candidate returned non-dict")

        # Attach IDs for traceability
        row.setdefault("trial_id", trial_id)
        row.setdefault("model_path", self.model_path)
        row.setdefault("worker_path", self.worker_path)

        # Objectives (min)
        y: List[float] = []
        for k in self.cfg0.objective_keys:
            v = _safe_float(row.get(k, float("inf")), default=float("inf"))
            y.append(v)

        # Constraints (<=0 feasible). Here: penalty - tol
        pen = _safe_float(row.get(self.cfg0.penalty_key, float("inf")), default=float("inf"))
        g = [float(pen - float(self.cfg0.penalty_tol))]

        # Add convenience fields
        row.setdefault("penalty_tol", float(self.cfg0.penalty_tol))
        row.setdefault("feasible", bool(g[0] <= 0.0))

        # Ensure JSON-serializable numbers
        for k, v in list(row.items()):
            if isinstance(v, (np.floating, np.integer)):
                row[k] = v.item()

        return y, g, row


def sample_lhs(n: int, d: int, *, seed: int = 0) -> np.ndarray:
    """Latin Hypercube Sampling in [0,1]^d."""
    rng = np.random.default_rng(int(seed))
    X = np.zeros((int(n), int(d)), dtype=float)
    for j in range(int(d)):
        perm = rng.permutation(int(n))
        X[:, j] = (perm + rng.random(int(n))) / float(n)
    return X
