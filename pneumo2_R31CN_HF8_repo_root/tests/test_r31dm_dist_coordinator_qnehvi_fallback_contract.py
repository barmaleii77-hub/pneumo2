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


def _install_fake_distributed(monkeypatch) -> None:
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


def _base_args() -> SimpleNamespace:
    return SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        proposer="qnehvi",
        q=1,
        dask_scheduler="",
        dask_workers=0,
        dask_threads_per_worker=1,
        dask_memory_limit="",
        dask_dashboard_address="",
        max_inflight=0,
        seed=0,
        budget=2,
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=1,
        min_feasible=1,
        proposer_buffer=1,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=400,
        heuristic_explore=0.37,
    )


def _seed_one_done_trial(db: ExperimentDB, run_id: str, problem_hash: str, core: _DummyCore) -> None:
    x_done = [0.10, 0.90]
    params_done = core.u_to_params(x_done)
    res_done = db.reserve_trial(
        run_id=run_id,
        problem_hash=problem_hash,
        param_hash="qnehvi_fallback_seed_done",
        x_u=list(x_done),
        params=params_done,
    )
    db.mark_done(
        res_done.trial_id,
        y=[1.0, 2.0],
        g=[-0.15],
        metrics={"obj1": 1.0, "obj2": 2.0, "penalty_total": -0.15},
    )


def test_r31dm_dask_qnehvi_failure_falls_back_to_heuristic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_distributed(monkeypatch)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    q_calls = {"n": 0}
    h_calls = {"n": 0}

    def fake_propose_qnehvi(**kwargs):  # noqa: ARG001
        q_calls["n"] += 1
        raise RuntimeError("forced qnehvi failure")

    def fake_propose_heuristic(**kwargs):
        h_calls["n"] += 1
        return SimpleNamespace(
            X=np.asarray([[0.25, 0.65]], dtype=float),
            meta={"method": "heuristic_after_qfail", "source": "r31dm_test"},
        )

    monkeypatch.setattr(coord, "propose_qnehvi", fake_propose_qnehvi)
    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_qfail_to_heur"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args()
    core = _DummyCore(dim=2)

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31dm_qh", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31dm_qh", core)
        coord._run_dask(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31dm_qh",
            objective_keys=["obj1", "obj2"],
        )

    assert q_calls["n"] >= 1
    assert h_calls["n"] >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "qnehvi"
    assert meta["effective_mode"] == "heuristic"
    assert meta["fallback_reason"] == "qnehvi_failed"
    assert "RuntimeError" in str(meta.get("fallback_error") or "")
    assert meta["method"] == "heuristic_after_qfail"
    assert (run_dir / "export" / "trials.csv").exists()


def test_r31dm_dask_qnehvi_and_heuristic_failure_fall_back_to_random(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_distributed(monkeypatch)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    q_calls = {"n": 0}
    h_calls = {"n": 0}

    def fake_propose_qnehvi(**kwargs):  # noqa: ARG001
        q_calls["n"] += 1
        raise RuntimeError("forced qnehvi failure")

    def fake_propose_heuristic(**kwargs):  # noqa: ARG001
        h_calls["n"] += 1
        raise ValueError("forced heuristic failure")

    monkeypatch.setattr(coord, "propose_qnehvi", fake_propose_qnehvi)
    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_qh_fail_to_random"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args()
    core = _DummyCore(dim=2)

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31dm_qhr", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31dm_qhr", core)
        coord._run_dask(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31dm_qhr",
            objective_keys=["obj1", "obj2"],
        )

    assert q_calls["n"] >= 1
    assert h_calls["n"] >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "qnehvi"
    assert meta["effective_mode"] == "random"
    assert meta["reason"] == "qnehvi_and_heuristic_failed"
    err = str(meta.get("fallback_error") or "")
    assert "RuntimeError" in err
    assert "ValueError" in err
    assert (run_dir / "export" / "trials.csv").exists()
