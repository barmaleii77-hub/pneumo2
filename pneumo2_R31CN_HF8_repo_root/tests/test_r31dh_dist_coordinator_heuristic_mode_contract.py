from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
from pneumo_solver_ui.tools import dist_opt_coordinator as coord


class _DummyCore:
    def __init__(self, dim: int = 2) -> None:
        self._dim = int(dim)

    def dim(self) -> int:
        return int(self._dim)

    def u_to_params(self, x_u: list[float]) -> dict[str, float]:
        return {f"x{i}": float(v) for i, v in enumerate(list(x_u))}


def test_r31dh_dask_runner_uses_heuristic_proposer_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_distributed = ModuleType("distributed")

    class FakeFuture:
        def __init__(self, x_u: list[float]) -> None:
            self._x = [float(v) for v in list(x_u)]

        def result(self):
            y = [float(self._x[0]), float(self._x[1])]
            g = [0.0]
            row = {"obj1": y[0], "obj2": y[1], "penalty_total": 0.0}
            return y, g, row

    class FakeLocalCluster:
        def __init__(self, **_kwargs) -> None:
            pass

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def scheduler_info(self) -> dict[str, object]:
            return {"workers": {"w0": {}}}

        def submit(self, _fn, _trial_id, x_u, pure=False):  # noqa: ARG002
            return FakeFuture(list(x_u))

        def close(self) -> None:
            pass

    class FakeAsCompleted:
        def __init__(self) -> None:
            self._items: list[object] = []

        def add(self, future: object) -> None:
            self._items.append(future)

        def __iter__(self):
            return self

        def __next__(self) -> object:
            if not self._items:
                raise StopIteration
            return self._items.pop(0)

    def fake_as_completed(_items: list[object]) -> FakeAsCompleted:
        return FakeAsCompleted()

    fake_distributed.Client = FakeClient
    fake_distributed.LocalCluster = FakeLocalCluster
    fake_distributed.as_completed = fake_as_completed
    monkeypatch.setitem(sys.modules, "distributed", fake_distributed)

    # Ensure buffer fill reaches proposer branch directly (no LHS warmup candidates).
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    calls: list[dict[str, object]] = []

    def fake_propose_heuristic(
        *,
        X_done,
        Y_min_done,
        penalty,
        q,
        seed,
        X_pending=None,
        feasible_tol=1e-9,
        pool_size=256,
        explore_weight=0.70,
    ):
        calls.append(
            {
                "X_done_shape": tuple(np.asarray(X_done).shape),
                "Y_min_shape": tuple(np.asarray(Y_min_done).shape),
                "penalty_is_none": penalty is None,
                "q": int(q),
                "seed": int(seed),
                "X_pending_is_none": X_pending is None,
                "feasible_tol": float(feasible_tol),
                "pool_size": int(pool_size),
                "explore_weight": float(explore_weight),
            }
        )
        return SimpleNamespace(
            X=np.asarray([[0.2, 0.8]], dtype=float),
            meta={"method": "heuristic_mock", "source": "r31dh_test"},
        )

    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_heuristic"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        proposer="heuristic",
        q=1,
        dask_scheduler="",
        dask_workers=0,
        dask_threads_per_worker=1,
        dask_memory_limit="",
        dask_dashboard_address="",
        max_inflight=0,
        seed=0,
        budget=1,
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=16,
        min_feasible=0,
        proposer_buffer=1,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=777,
        heuristic_explore=0.23,
    )

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31dh", spec={}, meta={"source": "test"})
        coord._run_dask(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31dh",
            objective_keys=["obj1", "obj2"],
        )

    assert calls, "heuristic proposer must be called at least once"
    call = calls[0]
    assert call["X_done_shape"] == (0, 2)
    assert call["Y_min_shape"] == (0, 2)
    assert call["penalty_is_none"] is True
    assert call["q"] == 1
    assert call["pool_size"] == 777
    assert abs(float(call["explore_weight"]) - 0.23) < 1e-12

    meta_path = run_dir / "last_proposer_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "heuristic"
    assert meta["effective_mode"] == "heuristic"
    assert meta["method"] == "heuristic_mock"

    assert (run_dir / "export" / "trials.csv").exists()
