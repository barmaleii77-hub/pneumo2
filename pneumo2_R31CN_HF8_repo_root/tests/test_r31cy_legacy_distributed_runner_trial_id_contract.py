from __future__ import annotations

from typing import Any, Dict

from pneumo_solver_ui.tools.run_dask_distributed_opt import (
    _dask_eval_wrapper,
    _request_idx_from_trial_id as dask_request_idx,
    _row_from_evaluator as dask_row_from_evaluator,
)
from pneumo_solver_ui.tools.run_ray_distributed_opt import (
    _request_idx_from_trial_id as ray_request_idx,
    _row_from_evaluator as ray_row_from_evaluator,
)


class _FakeEvaluator:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def evaluate(self, trial_id: str, x_u, idx: int = 0) -> Dict[str, Any]:
        return {
            "status": "done",
            "obj1": 1.0,
            "obj2": 2.0,
            "penalty": 0.0,
            "metrics": {"idx": int(idx)},
            "trial_id": str(trial_id),
        }

    def denormalize(self, x_u) -> Dict[str, float]:
        vals = [float(v) for v in x_u]
        return {f"x{i}": v for i, v in enumerate(vals)}


def test_r31cy_request_idx_supports_uuid_like_trial_ids() -> None:
    trial_id = "a1b2c3d4e5f60123456789abcdef0123"
    assert dask_request_idx("123", fallback=9) == 123
    assert ray_request_idx("123", fallback=9) == 123
    assert dask_request_idx(trial_id, fallback=9) == int("a1b2c3d4", 16)
    assert ray_request_idx(trial_id, fallback=9) == int("a1b2c3d4", 16)
    assert dask_request_idx("", fallback=9) == 9
    assert ray_request_idx("", fallback=9) == 9


def test_r31cy_row_helpers_keep_string_trial_ids() -> None:
    trial_id = "abcde12345ff00112233445566778899"
    row_dask = dask_row_from_evaluator(
        _FakeEvaluator(),
        trial_id=trial_id,
        param_hash="ph1",
        x_u=[0.1, 0.2],
        idx=7,
        worker_id="dask",
    )
    row_ray = ray_row_from_evaluator(
        _FakeEvaluator(),
        trial_id=trial_id,
        param_hash="ph1",
        x_u=[0.1, 0.2],
        idx=8,
        worker_id="ray_actor_0",
    )

    assert row_dask["trial_id"] == trial_id
    assert row_dask["idx"] == 7
    assert row_dask["worker_id"] == "dask"
    assert row_ray["trial_id"] == trial_id
    assert row_ray["idx"] == 8
    assert row_ray["worker_id"] == "ray_actor_0"


def test_r31cy_dask_wrapper_accepts_string_trial_id(monkeypatch) -> None:
    import pneumo_solver_ui.pneumo_dist.eval_core as eval_core

    monkeypatch.setattr(eval_core, "Evaluator", _FakeEvaluator)
    trial_id = "00aa11bb22cc33dd44ee55ff66778899"

    row = _dask_eval_wrapper(
        model_py="model.py",
        worker_py="worker.py",
        base_json=None,
        ranges_json=None,
        suite_json=None,
        cfg_extra={},
        trial_id=trial_id,
        param_hash="ph2",
        x_u=[0.25, 0.75],
        idx=13,
    )

    assert row["trial_id"] == trial_id
    assert row["idx"] == 13
    assert row["worker_id"] == "dask"
