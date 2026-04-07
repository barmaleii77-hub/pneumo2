# -*- coding: utf-8 -*-
"""Evaluation core for distributed runners.

We intentionally *reuse* the existing local worker implementation
(`opt_worker_v3_margins_energy.py`) so that distributed runs produce the
same KPIs/objectives as the UI / local single-PC mode.

The evaluator:
- loads base/ranges/suite JSON,
- maps normalized vectors x_u in [0,1]^d -> SI parameters,
- calls `eval_candidate` from the worker,
- extracts objectives/penalty.

No external dependencies.
"""

from __future__ import annotations

import importlib.util
import json
import os
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Sequence


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_module_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def load_base_and_ranges(worker_py: str, base_json: Optional[str] = None, ranges_json: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Tuple[float, float]], str, str]:
    wdir = os.path.dirname(os.path.abspath(worker_py))
    base_path = base_json or os.path.join(wdir, "default_base.json")
    ranges_path = ranges_json or os.path.join(wdir, "default_ranges.json")

    base = load_json(base_path)
    ranges_raw = load_json(ranges_path)

    ranges: Dict[str, Tuple[float, float]] = {}
    for k, v in ranges_raw.items():
        if (not isinstance(v, (list, tuple))) or len(v) != 2:
            raise ValueError(f"Range '{k}' must be [min,max], got {v}")
        ranges[str(k)] = (float(v[0]), float(v[1]))
    return base, ranges, base_path, ranges_path


def load_suite(worker_py: str, suite_json: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    wdir = os.path.dirname(os.path.abspath(worker_py))
    suite_path = suite_json or os.path.join(wdir, "default_suite.json")
    suite = load_json(suite_path)
    if not isinstance(suite, list):
        raise ValueError(f"suite must be a list, got {type(suite)}")
    return suite, suite_path


def denormalize(x_u: List[float], ranges: Dict[str, Tuple[float, float]], keys: List[str]) -> Dict[str, float]:
    params: Dict[str, float] = {}
    if len(x_u) != len(keys):
        raise ValueError(f"x_u dim mismatch: got {len(x_u)}, expected {len(keys)}")
    for i, k in enumerate(keys):
        lo, hi = ranges[k]
        u = float(x_u[i])
        if u < 0.0:
            u = 0.0
        if u > 1.0:
            u = 1.0
        params[k] = float(lo + u * (hi - lo))
    return params


def normalize_from_params(params: Dict[str, Any], ranges: Dict[str, Tuple[float, float]], keys: List[str]) -> List[float]:
    out: List[float] = []
    for k in keys:
        lo, hi = ranges[k]
        v = float(params[k])
        if abs(hi - lo) < 1e-30:
            out.append(0.0)
        else:
            out.append(float((v - lo) / (hi - lo)))
    return out


@dataclass
class EvalResult:
    metrics: Dict[str, Any]
    obj1: float
    obj2: float
    penalty: float
    status: str
    error: str = ""
    traceback: str = ""


class Evaluator:
    def __init__(
        self,
        *,
        model_py: str,
        worker_py: str,
        base_json: Optional[str] = None,
        ranges_json: Optional[str] = None,
        suite_json: Optional[str] = None,
        cfg_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.model_py = os.path.abspath(model_py)
        self.worker_py = os.path.abspath(worker_py)

        # import worker + model
        self.worker = import_module_from_path("pneumo_worker", self.worker_py)
        self.model = self.worker.load_model(self.model_py)

        self.base, self.ranges, self.base_path, self.ranges_path = load_base_and_ranges(self.worker_py, base_json, ranges_json)
        self.suite, self.suite_path = load_suite(self.worker_py, suite_json)

        self.keys = list(self.ranges.keys())

        # cfg
        cfg: Dict[str, Any] = {
            "suite": self.suite,
            "dt": 0.003,
            "t_step": 0.4,
            "t_end_short": 1.2,
            "t_end_inertia": 1.2,
            "t_end_micro": 1.6,
            "settle_band_min_deg": 0.5,
            "settle_band_ratio": 0.20,
            "колея": float(self.base.get("колея", 1.0)),
            "база": float(self.base.get("база", 1.5)),
            "скорость_м_с_по_умолчанию": float(self.base.get("скорость_м_с_по_умолчанию", 10.0)),
        }
        if cfg_overrides:
            cfg.update(cfg_overrides)
        self.cfg = cfg


    # -----------------------
    # Convenience helpers
    # -----------------------

    @property
    def dim(self) -> int:
        return int(len(self.keys))

    @property
    def param_order(self) -> List[str]:
        """Backward-compatible name used by some scripts."""
        return list(self.keys)

    def denormalize(self, x_u: Sequence[float]) -> Dict[str, float]:
        """Map x_u in [0,1]^d -> partial params dict (design variables only)."""
        return denormalize(list(x_u), self.ranges, self.keys)

    def normalize(self, params_partial: Dict[str, Any]) -> List[float]:
        """Map partial params dict -> x_u in [0,1]^d."""
        return normalize_from_params(params_partial, self.ranges, self.keys)

    def bounds_u(self):
        """Return bounds in normalized space as (2,d) numpy array."""
        import numpy as np

        return np.stack([np.zeros(self.dim, dtype=float), np.ones(self.dim, dtype=float)], axis=0)


    def make_full_params(self, params_partial: Dict[str, Any]) -> Dict[str, Any]:
        p = dict(self.base)
        p.update(params_partial)
        return p

    def eval_xu(self, idx: int, x_u: List[float]) -> EvalResult:
        try:
            params_partial = denormalize(x_u, self.ranges, self.keys)
            params_full = self.make_full_params(params_partial)
            row = self.worker.eval_candidate(self.model, idx=idx, params=params_full, cfg=self.cfg)
            obj1 = float(row.get("цель1_устойчивость_инерция__с", float("nan")))
            obj2 = float(row.get("цель2_комфорт__RMS_ускор_м_с2", float("nan")))
            pen = float(row.get("штраф_физичности_сумма", float("nan")))
            return EvalResult(metrics=row, obj1=obj1, obj2=obj2, penalty=pen, status="done")
        except Exception as e:
            tb = traceback.format_exc()
            return EvalResult(metrics={}, obj1=float("nan"), obj2=float("nan"), penalty=float("nan"), status="error", error=str(e), traceback=tb)

    def eval_params(self, idx: int, params: Dict[str, Any]) -> EvalResult:
        try:
            params_full = self.make_full_params(params)
            row = self.worker.eval_candidate(self.model, idx=idx, params=params_full, cfg=self.cfg)
            obj1 = float(row.get("цель1_устойчивость_инерция__с", float("nan")))
            obj2 = float(row.get("цель2_комфорт__RMS_ускор_м_с2", float("nan")))
            pen = float(row.get("штраф_физичности_сумма", float("nan")))
            return EvalResult(metrics=row, obj1=obj1, obj2=obj2, penalty=pen, status="done")
        except Exception as e:
            tb = traceback.format_exc()
            return EvalResult(metrics={}, obj1=float("nan"), obj2=float("nan"), penalty=float("nan"), status="error", error=str(e), traceback=tb)
