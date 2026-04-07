# -*- coding: utf-8 -*-
"""Stable hashing helpers for experiment dedup.

We need deterministic hashes across machines and runs.
The hash should NOT depend on absolute file paths (they differ between PCs),
only on file content + structured config.

Implementation notes:
- We JSON-dump dicts with sorted keys.
- Floats are quantized to a reasonable precision (12 significant digits)
  before hashing to avoid platform-specific repr differences.

"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict


def _qfloat(x: float) -> str:
    """Quantize float to stable string."""
    # 12 significant digits: usually enough for design variables,
    # and stable across platforms.
    try:
        return format(float(x), ".12g")
    except Exception:
        return str(x)


def _normalize(obj: Any) -> Any:
    """Recursively normalize python object for stable hashing."""
    if obj is None:
        return None
    if isinstance(obj, (bool, int)):
        return obj
    if isinstance(obj, float):
        # keep as string to avoid JSON float formatting differences
        return {"__float__": _qfloat(obj)}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    # numpy scalars / other numeric types
    try:
        import numpy as np  # type: ignore

        if isinstance(obj, (np.floating,)):
            return {"__float__": _qfloat(float(obj))}
        if isinstance(obj, (np.integer,)):
            return int(obj)
    except Exception:
        pass

    # fallback: stable string
    return str(obj)


def stable_json_dumps(obj: Any) -> str:
    """Deterministic JSON dumps."""
    norm = _normalize(obj)
    return json.dumps(norm, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: str | os.PathLike) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash_params(params: Dict[str, Any]) -> str:
    """Hash for candidate parameters."""
    return sha256_text(stable_json_dumps(params))


def stable_hash_problem(
    *,
    model_py: str,
    worker_py: str | None = None,
    base: Dict[str, Any] | None = None,
    ranges: Dict[str, Any] | None = None,
    suite: Any | None = None,
    extra: Dict[str, Any] | None = None,
) -> str:
    """Hash for the *problem definition*.

    Includes:
    - model file content hash
    - worker file content hash (if provided)
    - base/ranges/suite structures
    - extra user config

    Does NOT include absolute paths.
    """
    payload: Dict[str, Any] = {
        "model_sha256": sha256_file(model_py),
    }
    if worker_py:
        payload["worker_sha256"] = sha256_file(worker_py)
    if base is not None:
        payload["base"] = base
    if ranges is not None:
        payload["ranges"] = ranges
    if suite is not None:
        payload["suite"] = suite
    if extra is not None:
        payload["extra"] = extra

    return sha256_text(stable_json_dumps(payload))

# -----------------------------------------------------------------------------
# Convenience aliases (used by coordinator scripts)
# -----------------------------------------------------------------------------

def stable_hash_file(path: str | os.PathLike) -> str:
    """Alias for sha256_file (kept for backward compatibility)."""
    return sha256_file(path)


def stable_hash_json_file(path: str | os.PathLike) -> str:
    """Stable hash for a JSON file (content, not path)."""
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    return sha256_text(stable_json_dumps(obj))
