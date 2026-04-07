# -*- coding: utf-8 -*-
"""pneumo_dist

Distributed optimization / experiment-tracking layer.

Design goals:
- single-writer DB (coordinator) for robustness on Windows and embedded DB engines;
- pluggable backends (Ray / Dask);
- optional BoTorch MOBO proposer (GPU-friendly);
- reuse existing model + opt_worker evaluation logic.

This package is intentionally dependency-light. Heavy deps (ray, dask, torch, botorch,
duckdb) are optional and imported lazily.
"""

from __future__ import annotations

__all__ = [
    "trial_hash",
    "expdb",
    "eval_core",
    "hv_tools",
    "mobo_propose",
]
