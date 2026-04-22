from __future__ import annotations

from typing import Any, Dict

from pneumo_solver_ui.tools.run_dask_distributed_async import (
    _EVAL_CACHE,
    _eval_task,
    _request_idx_from_trial_id as dask_request_idx,
    _row_from_evaluator as dask_row_from_evaluator,
)
from pneumo_solver_ui.tools.run_ray_distributed_async import (
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
            "obj1": 3.0,
            "obj2": 4.0,
            "penalty": 0.1,
            "metrics": {"idx": int(idx)},
            "trial_id": str(trial_id),
        }

    def denormalize(self, x_u) -> Dict[str, float]:
        vals = [float(v) for v in x_u]
        return {f"x{i}": v for i, v in enumerate(vals)}


def test_r31cz_request_idx_supports_uuid_like_trial_ids() -> None:
    trial_id = "f0e1d2c3b4a5968778695a4b3c2d1e0f"
    assert dask_request_idx("123", fallback=9) == 123
    assert ray_request_idx("123", fallback=9) == 123
    assert dask_request_idx(trial_id, fallback=9) == int("f0e1d2c3", 16)
    assert ray_request_idx(trial_id, fallback=9) == int("f0e1d2c3", 16)
    assert dask_request_idx("", fallback=9) == 9
    assert ray_request_idx("", fallback=9) == 9


def test_r31cz_row_helpers_keep_string_trial_ids() -> None:
    trial_id = "00112233445566778899aabbccddeeff"
    row_dask = dask_row_from_evaluator(
        _FakeEvaluator(),
        trial_id=trial_id,
        param_hash="ph_async",
        x_u=[0.1, 0.9],
        idx=5,
        worker_id="dask",
    )
    row_ray = ray_row_from_evaluator(
        _FakeEvaluator(),
        trial_id=trial_id,
        param_hash="ph_async",
        x_u=[0.1, 0.9],
        idx=6,
        worker_id="ray",
    )

    assert row_dask["trial_id"] == trial_id
    assert row_dask["idx"] == 5
    assert row_dask["worker_id"] == "dask"
    assert row_ray["trial_id"] == trial_id
    assert row_ray["idx"] == 6
    assert row_ray["worker_id"] == "ray"


def test_r31cz_dask_eval_task_accepts_string_trial_id(monkeypatch) -> None:
    import pneumo_solver_ui.tools.run_dask_distributed_async as dask_async_mod

    monkeypatch.setattr(dask_async_mod, "Evaluator", _FakeEvaluator)
    _EVAL_CACHE.clear()

    trial_id = "aa11bb22cc33dd44ee55ff6677889900"
    row = _eval_task(
        model_py="model.py",
        worker_py="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        trial_id=trial_id,
        param_hash="ph_eval_task",
        x_u=[0.3, 0.7],
        idx=11,
    )

    assert row["trial_id"] == trial_id
    assert row["idx"] == 11
    assert row["worker_id"] == "dask"
