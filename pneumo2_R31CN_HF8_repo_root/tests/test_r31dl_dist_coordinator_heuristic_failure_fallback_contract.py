from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

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


def test_r31dl_dask_heuristic_failure_falls_back_to_random(
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

    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    def fake_propose_heuristic(**kwargs):  # noqa: ARG001
        raise RuntimeError("forced heuristic failure")

    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_heuristic_fail"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = type("Args", (), {})()
    args.model = "model.py"
    args.worker = "worker.py"
    args.base_json = ""
    args.ranges_json = ""
    args.suite_json = ""
    args.penalty_key = "penalty_total"
    args.penalty_tol = 0.0
    args.proposer = "heuristic"
    args.q = 1
    args.dask_scheduler = ""
    args.dask_workers = 0
    args.dask_threads_per_worker = 1
    args.dask_memory_limit = ""
    args.dask_dashboard_address = ""
    args.max_inflight = 0
    args.seed = 0
    args.budget = 1
    args.seed_json = ""
    args.resume = False
    args.stale_ttl_sec = 600
    args.hv_log = False
    args.export_every = 0
    args.n_init = 16
    args.min_feasible = 0
    args.proposer_buffer = 1
    args.device = "auto"
    args.botorch_no_normalize_objectives = False
    args.botorch_ref_margin = 0.1
    args.botorch_num_restarts = 10
    args.botorch_raw_samples = 512
    args.botorch_maxiter = 200
    args.heuristic_pool_size = 333
    args.heuristic_explore = 0.44

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31dl", spec={}, meta={"source": "test"})
        coord._run_dask(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31dl",
            objective_keys=["obj1", "obj2"],
        )

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "heuristic"
    assert meta["effective_mode"] == "random"
    assert meta["reason"] == "heuristic_failed"
    assert "RuntimeError" in str(meta.get("fallback_error") or "")
    assert (run_dir / "export" / "trials.csv").exists()
