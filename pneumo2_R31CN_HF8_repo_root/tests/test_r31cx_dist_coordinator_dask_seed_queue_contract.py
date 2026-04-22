from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
from pneumo_solver_ui.tools.dist_opt_coordinator import _run_dask


class _DummyCore:
    def __init__(self, dim: int = 2) -> None:
        self._dim = int(dim)

    def dim(self) -> int:
        return int(self._dim)

    def u_to_params(self, x_u: list[float]) -> dict[str, float]:
        return {f"x{i}": float(v) for i, v in enumerate(list(x_u))}


def test_r31cx_dask_runner_initializes_seed_queue_for_new_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_distributed = ModuleType("distributed")

    class FakeLocalCluster:
        def __init__(self, **_kwargs) -> None:
            pass

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def scheduler_info(self) -> dict[str, object]:
            return {"workers": {}}

        def close(self) -> None:
            pass

    class FakeAsCompleted:
        def add(self, _future: object) -> None:
            pass

        def __iter__(self):
            return self

        def __next__(self) -> object:
            raise StopIteration

    def fake_as_completed(_items: list[object]) -> FakeAsCompleted:
        return FakeAsCompleted()

    fake_distributed.Client = FakeClient
    fake_distributed.LocalCluster = FakeLocalCluster
    fake_distributed.as_completed = fake_as_completed
    monkeypatch.setitem(sys.modules, "distributed", fake_distributed)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        dask_scheduler="",
        dask_workers=0,
        dask_threads_per_worker=1,
        dask_memory_limit="",
        dask_dashboard_address="",
        max_inflight=0,
        seed=0,
        budget=0,
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=16,
        proposer_buffer=8,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
    )

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31cx", spec={}, meta={"source": "test"})
        _run_dask(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31cx",
            objective_keys=["obj1", "obj2"],
        )

    assert (run_dir / "dask_scheduler_info.json").exists()
    assert (run_dir / "export" / "trials.csv").exists()
    assert (run_dir / "export" / "run_metrics.csv").exists()
