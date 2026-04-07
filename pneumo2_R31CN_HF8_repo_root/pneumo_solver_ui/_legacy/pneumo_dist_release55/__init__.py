"""pneumo_dist

Distributed optimization / evaluation utilities.

Design goals:
- Optional dependencies (Ray/Dask/DuckDB/BoTorch).
- Single-writer experiment DB for reproducibility and dedup.
- Works on Windows and Linux.

The package name intentionally avoids "distributed" to not conflict with
"dask.distributed" (module name: distributed).
"""

from .trial_hash import stable_hash_params, stable_hash_problem
from .expdb import ExperimentDB

__all__ = [
    "stable_hash_params",
    "stable_hash_problem",
    "ExperimentDB",
]
