# -*- coding: utf-8 -*-
"""pneumo_dist.trial_hash

Stable hashing utilities for experiment reproducibility and deduplication.

We hash:
- **problem definition** (model file content, worker version, cfg, base/ranges/suite),
- **candidate parameters** (dict of floats / ints).

Key points:
- JSON is deterministic when we:
  - sort keys,
  - keep stable separators,
  - normalize floats (rounding) and numpy scalars.
- We intentionally avoid pickle: it is not stable across Python versions.

This is not crypto-security code; it's for stable IDs.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


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
    """Recursively normalize python objects into JSON-friendly, stable structures."""
    obj = _to_py_scalar(obj)

    if obj is None:
        return None

    if isinstance(obj, bool):
        return bool(obj)

    if isinstance(obj, int):
        return int(obj)

    if isinstance(obj, float):
        # -0.0 vs 0.0 normalization
        v = float(round(obj, float_ndigits))
        if v == 0.0:
            v = 0.0
        return v

    if isinstance(obj, str):
        return obj

    if isinstance(obj, (list, tuple)):
        return [normalize_for_hash(x, float_ndigits=float_ndigits) for x in obj]

    if isinstance(obj, set):
        # stable order
        return [normalize_for_hash(x, float_ndigits=float_ndigits) for x in sorted(obj)]

    if isinstance(obj, dict):
        # keys to strings
        out: Dict[str, Any] = {}
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            out[str(k)] = normalize_for_hash(obj[k], float_ndigits=float_ndigits)
        return out

    # Fallback: try stringify (keeps reproducibility for unknown types)
    return str(obj)


def canonical_dumps(obj: Any, *, float_ndigits: int = 12) -> str:
    """Canonical JSON string for hashing."""
    norm = normalize_for_hash(obj, float_ndigits=float_ndigits)
    return json.dumps(norm, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(s: str) -> str:
    return sha256_hex(s.encode("utf-8"))


def hash_file(path: str | os.PathLike) -> str:
    """SHA256 of file contents."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_params(params: Mapping[str, Any], *, float_ndigits: int = 12) -> str:
    """Hash candidate parameters dict."""
    s = canonical_dumps(dict(params), float_ndigits=float_ndigits)
    return sha256_str(s)


def hash_vector(x: Sequence[float], *, float_ndigits: int = 12) -> str:
    """Hash a vector of floats (e.g., normalized design X in [0,1]^d)."""
    s = canonical_dumps(list(x), float_ndigits=float_ndigits)
    return sha256_str(s)


@dataclass(frozen=True)
class ProblemSpec:
    """A minimal, serializable definition of the optimization problem."""

    model_path: str
    worker_path: str
    base_json: str | None = None
    ranges_json: str | None = None
    suite_json: str | None = None
    cfg: Dict[str, Any] | None = None
    # For reproducibility / resume checks
    model_sha256: str | None = None
    worker_sha256: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_path": self.model_path,
            "worker_path": self.worker_path,
            "base_json": self.base_json,
            "ranges_json": self.ranges_json,
            "suite_json": self.suite_json,
            "cfg": self.cfg or {},
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
    cfg: Dict[str, Any] | None,
    include_file_hashes: bool = True,
) -> ProblemSpec:
    model_sha = hash_file(model_path) if include_file_hashes else None
    worker_sha = hash_file(worker_path) if include_file_hashes else None
    return ProblemSpec(
        model_path=str(model_path),
        worker_path=str(worker_path),
        base_json=str(base_json) if base_json else None,
        ranges_json=str(ranges_json) if ranges_json else None,
        suite_json=str(suite_json) if suite_json else None,
        cfg=cfg or {},
        model_sha256=model_sha,
        worker_sha256=worker_sha,
    )


def hash_problem(spec: ProblemSpec, *, float_ndigits: int = 12) -> str:
    """Hash of the full problem definition."""
    s = canonical_dumps(spec.to_dict(), float_ndigits=float_ndigits)
    return sha256_str(s)
