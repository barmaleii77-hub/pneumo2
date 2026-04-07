"""trial_hash.py

Centralized hashing utilities used by distributed optimization.

The project historically accumulated multiple call-sites for *problem hashing*.
Some scripts call hash_problem(ProblemSpec), others call stable_hash_problem(model_py=..., ...).

This module keeps backward compatibility **and** provides a stable, content-based hash mode.

Hash mode control:
  - PNEUMO_OPT_PROBLEM_HASH_MODE=stable   (default)
  - PNEUMO_OPT_PROBLEM_HASH_MODE=legacy

Stable mode hashes:
  - model/worker code sha256
  - the fixed part of base.json (excluding keys present in ranges.json)
  - the set of optimizable keys
  - suite.json (structure/content)
  - the explicit objective / penalty contract (objective_keys, penalty_key, penalty_tol)
  - extra (optional) if provided

Legacy mode hashes:
  - ProblemSpec.to_dict() (paths + cfg + code sha), same as hash_problem

"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


def _to_py_scalar(x: Any) -> Any:
    """Convert numpy scalars to python scalars if numpy is available."""
    try:
        import numpy as np  # type: ignore

        if isinstance(x, (np.floating, np.integer)):
            return x.item()
    except Exception:
        pass
    return x


def normalize_for_hash(obj: Any, *, float_ndigits: int = 12) -> Any:
    """Normalize for stable hashing (float and Path handling)."""
    obj = _to_py_scalar(obj)
    if isinstance(obj, dict):
        return {k: normalize_for_hash(v, float_ndigits=float_ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize_for_hash(x, float_ndigits=float_ndigits) for x in obj]
    if isinstance(obj, float):
        # Stable float stringification with caller-controlled precision for back-compat
        return float(f"{obj:.{int(float_ndigits)}g}")
    if isinstance(obj, Path):
        return obj.as_posix()
    return obj


def canonical_dumps(obj: Any, *, float_ndigits: int = 12) -> str:
    return json.dumps(
        normalize_for_hash(obj, float_ndigits=float_ndigits),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hash_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# Back-compat alias (some branches used this name)
file_sha256 = hash_file


@dataclass(frozen=True)
class ProblemSpec:
    model_path: str
    worker_path: str
    base_json: str
    ranges_json: str
    suite_json: str
    cfg: Dict[str, Any]
    model_sha256: str
    worker_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_path": self.model_path,
            "worker_path": self.worker_path,
            "base_json": self.base_json,
            "ranges_json": self.ranges_json,
            "suite_json": self.suite_json,
            "cfg": self.cfg,
            "model_sha256": self.model_sha256,
            "worker_sha256": self.worker_sha256,
        }


def make_problem_spec(
    *,
    model_path: str,
    worker_path: str,
    base_json: str | None,
    ranges_json: str | None,
    suite_json: str | None,
    cfg: Dict[str, Any],
    include_file_hashes: bool = True,
) -> ProblemSpec:
    model_p = Path(model_path)
    worker_p = Path(worker_path)

    model_sha = hash_file(model_p) if include_file_hashes else ""
    worker_sha = hash_file(worker_p) if include_file_hashes else ""

    return ProblemSpec(
        model_path=str(model_p),
        worker_path=str(worker_p),
        base_json=str(base_json or ""),
        ranges_json=str(ranges_json or ""),
        suite_json=str(suite_json or ""),
        cfg=dict(cfg),
        model_sha256=model_sha,
        worker_sha256=worker_sha,
    )


def hash_params(params: Dict[str, Any], *, float_ndigits: int = 12) -> str:
    """Stable hash of candidate parameters with optional float precision control."""
    payload = {
        "v": 1,
        "params": params,
    }
    return sha256_str(canonical_dumps(payload, float_ndigits=float_ndigits))



def hash_vector(x: Sequence[float], *, float_ndigits: int = 12) -> str:
    """Stable hash of a numeric vector (used for caching)."""
    # Normalize floats to reduce platform noise
    xs = [float(f"{float(v):.{float_ndigits}g}") for v in x]
    payload = {"v": 1, "x": xs}
    return sha256_str(canonical_dumps(payload, float_ndigits=float_ndigits))


def stable_hash_params(params: Dict[str, Any], keys: Optional[Sequence[str]] = None, *, float_ndigits: int = 12) -> str:
    """Stable hashing for a parameter dict.

    If `keys` is provided, only those keys are included (missing keys are ignored).
    """
    if keys is None:
        sub = params
    else:
        sub = {k: params.get(k) for k in keys if k in params}
    return hash_params(sub, float_ndigits=float_ndigits)


def hash_problem(spec: ProblemSpec, *, float_ndigits: int = 12) -> str:
    return sha256_str(canonical_dumps(spec.to_dict(), float_ndigits=float_ndigits))


def _safe_load_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not str(p):
        return {}
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        try:
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def _stable_problem_extra_from_cfg(cfg: Any) -> Dict[str, Any]:
    """Return the safe config subset that must participate in stable problem hashing.

    Budgets, backend knobs and proposer settings must *not* change ``problem_hash``.
    The optimization *quality contract* must change it, otherwise resume/cache can
    silently mix runs that optimize or gate candidates under different semantics.
    """
    if not isinstance(cfg, dict):
        return {}
    extra: Dict[str, Any] = {}

    objective_keys = cfg.get('objective_keys')
    if isinstance(objective_keys, Sequence) and not isinstance(objective_keys, (str, bytes, bytearray)):
        extra['objective_keys'] = list(objective_keys)

    penalty_key = str(cfg.get('penalty_key') or '').strip()
    if penalty_key:
        extra['penalty_key'] = penalty_key

    if 'penalty_tol' in cfg:
        try:
            extra['penalty_tol'] = float(cfg.get('penalty_tol'))
        except Exception:
            extra['penalty_tol'] = cfg.get('penalty_tol')

    penalty_targets = cfg.get('penalty_targets')
    if isinstance(penalty_targets, Sequence) and not isinstance(penalty_targets, (str, bytes, bytearray)):
        extra['penalty_targets'] = list(penalty_targets)

    return extra


def stable_hash_problem(*args, **kwargs) -> str:
    """Compatibility + stability wrapper for optimization problem hashing.

    Supported call forms:
      1) stable_hash_problem(spec: ProblemSpec) -> str
      2) stable_hash_problem(model_py=..., worker_py=..., base=..., ranges=..., suite=..., extra=None,
                             mode=None) -> str
      3) stable_hash_problem(base=..., ranges=..., suite=..., model_sha256=..., worker_sha256=...,
                             extra=None, mode=None) -> str

    Hash mode:
      - "stable" (default): hashes ONLY the fixed part of base (excluding keys present in ranges)
        + the set of optimizable keys + suite + model/worker sha + extra.
      - "legacy": hashes full ProblemSpec (paths + cfg + sha), i.e. old behaviour.

    Default mode can be controlled by env var:
        PNEUMO_OPT_PROBLEM_HASH_MODE=stable|legacy

    Notes:
      - This function returns full SHA256 hex (64 chars). Call-sites may slice it.

    """

    if len(args) == 1 and not kwargs and isinstance(args[0], ProblemSpec):
        spec: ProblemSpec = args[0]
        mode = os.environ.get("PNEUMO_OPT_PROBLEM_HASH_MODE", "stable").strip().lower()
        if mode in ("legacy", "old", "compat"):
            return hash_problem(spec)

        base = _safe_load_json(spec.base_json)
        ranges = _safe_load_json(spec.ranges_json)
        suite = _safe_load_json(spec.suite_json)
        # By default include only the safe subset of cfg that changes the
        # optimization semantics (objective / penalty contract), not backend budgets.
        try:
            extra = _stable_problem_extra_from_cfg(spec.cfg)
        except Exception:
            extra = {}

        model_sha = spec.model_sha256 or hash_file(spec.model_path)
        worker_sha = spec.worker_sha256 or hash_file(spec.worker_path)
        return stable_hash_problem(
            base=base,
            ranges=ranges,
            suite=suite,
            model_sha256=model_sha,
            worker_sha256=worker_sha,
            extra=extra,
            mode="stable",
        )

    if args:
        raise TypeError("stable_hash_problem supports only keyword args or a single ProblemSpec")

    mode = (kwargs.pop("mode", None) or os.environ.get("PNEUMO_OPT_PROBLEM_HASH_MODE", "stable")).strip().lower()
    extra = kwargs.get("extra") or {}

    if "model_sha256" in kwargs and "worker_sha256" in kwargs:
        model_sha = str(kwargs["model_sha256"])
        worker_sha = str(kwargs["worker_sha256"])
    else:
        model_py = Path(kwargs["model_py"]).resolve()
        worker_py = Path(kwargs["worker_py"]).resolve()
        model_sha = hash_file(model_py)
        worker_sha = hash_file(worker_py)

    base = kwargs["base"]
    ranges = kwargs["ranges"]
    suite = kwargs["suite"]

    if mode in ("legacy", "old", "compat"):
        payload = {
            "v": 0,
            "base": base,
            "ranges": ranges,
            "suite": suite,
            "model_sha256": model_sha,
            "worker_sha256": worker_sha,
            "extra": extra,
        }
        return sha256_str(canonical_dumps(payload))

    try:
        optim_keys = set(getattr(ranges, "keys")())  # type: ignore[arg-type]
    except Exception:
        optim_keys = set()

    try:
        base_sig = {k: base[k] for k in base.keys() if k not in optim_keys}  # type: ignore[attr-defined]
    except Exception:
        base_sig = base

    payload = {
        "v": 1,
        "base_signature": base_sig,
        "ranges_signature": sorted(list(optim_keys)),
        "suite_signature": suite,
        "model_sha256": model_sha,
        "worker_sha256": worker_sha,
        "extra": extra,
    }
    return sha256_str(canonical_dumps(payload))
