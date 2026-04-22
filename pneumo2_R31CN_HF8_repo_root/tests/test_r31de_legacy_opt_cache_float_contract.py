from __future__ import annotations

import math

from pneumo_solver_ui.tools.run_dask_distributed_opt import _safe_float as dask_safe_float
from pneumo_solver_ui.tools.run_ray_distributed_opt import _safe_float as ray_safe_float


def test_r31de_safe_float_handles_legacy_none_values() -> None:
    for fn in (ray_safe_float, dask_safe_float):
        assert math.isnan(fn(None))
        assert math.isnan(fn("not-a-number"))
        assert math.isnan(fn(object()))
        assert abs(fn("1.25") - 1.25) < 1e-12
        assert abs(fn(2) - 2.0) < 1e-12


def test_r31de_safe_float_preserves_cache_hit_flow_when_values_missing() -> None:
    legacy_cache = {"metrics": {"legacy": True}}
    for fn in (ray_safe_float, dask_safe_float):
        obj1 = fn(legacy_cache.get("obj1"))
        obj2 = fn(legacy_cache.get("obj2"))
        penalty = fn(legacy_cache.get("penalty"))
        assert math.isnan(obj1)
        assert math.isnan(obj2)
        assert math.isnan(penalty)
