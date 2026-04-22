from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Tuple

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


class _FakeEvaluatorCore:
    def __init__(
        self,
        model_path: str,
        worker_path: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
        cfg: Dict[str, Any] | None = None,
    ) -> None:
        _ = model_path, worker_path, base_json, ranges_json, suite_json, cfg

    def evaluate(self, trial_id: str, x_u: List[float]) -> Tuple[List[float], List[float], Dict[str, Any]]:
        arr = np.asarray(x_u, dtype=float).reshape(-1)
        y = [float(arr[0]), float(arr[1])]
        g = [0.0]
        row = {"trial_id": str(trial_id), "obj1": y[0], "obj2": y[1], "penalty_total": 0.0}
        return y, g, row


class _FakeRayRef:
    def __init__(self, value: Any = None, error: Exception | None = None):
        self.value = value
        self.error = error


def _fake_ray_result(fn, *args, **kwargs) -> _FakeRayRef:
    try:
        return _FakeRayRef(value=fn(*args, **kwargs))
    except Exception as exc:  # pragma: no cover - defensive
        return _FakeRayRef(error=exc)


class _FakeRayActorHandle:
    def __init__(self, inst: Any):
        self._inst = inst

    def __getattr__(self, name: str):
        attr = getattr(self._inst, name)
        if not callable(attr):
            return attr
        return SimpleNamespace(remote=lambda *a, **k: _fake_ray_result(attr, *a, **k))


def _make_fake_ray_module() -> ModuleType:
    mod = ModuleType("ray")

    def init(*args, **kwargs):
        _ = args, kwargs
        return None

    def cluster_resources() -> Dict[str, float]:
        # GPU>0 enables proposer actor pool path.
        return {"CPU": 1.0, "GPU": 1.0}

    def get_gpu_ids() -> List[int]:
        return [0]

    def remote(*r_args, **r_kwargs):
        _ = r_kwargs

        def decorate(obj):
            if isinstance(obj, type):
                cls = obj

                class _RemoteClass:
                    @staticmethod
                    def options(**_opts):
                        return _RemoteClass

                    @staticmethod
                    def remote(*a, **k):
                        return _FakeRayActorHandle(cls(*a, **k))

                return _RemoteClass

            fn = obj
            wrapped = lambda *a, **k: _fake_ray_result(fn, *a, **k)
            wrapped.remote = wrapped
            return wrapped

        if len(r_args) == 1 and callable(r_args[0]):
            return decorate(r_args[0])
        return decorate

    def wait(
        refs: List[_FakeRayRef],
        num_returns: int = 1,
        timeout: float | None = None,
    ) -> Tuple[List[_FakeRayRef], List[_FakeRayRef]]:
        _ = timeout
        if not refs:
            return [], []
        n = max(1, int(num_returns))
        return list(refs[:n]), list(refs[n:])

    def get(obj: Any) -> Any:
        if isinstance(obj, list):
            return [get(v) for v in obj]
        if isinstance(obj, _FakeRayRef):
            if obj.error is not None:
                raise obj.error
            return obj.value
        return obj

    mod.init = init
    mod.remote = remote
    mod.wait = wait
    mod.get = get
    mod.cluster_resources = cluster_resources
    mod.get_gpu_ids = get_gpu_ids
    return mod


def _base_args() -> SimpleNamespace:
    return SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        proposer="portfolio",
        q=1,
        ray_address="local",
        ray_runtime_env="off",
        ray_runtime_env_json="",
        ray_runtime_exclude=[],
        ray_local_num_cpus=0,
        ray_local_dashboard=False,
        ray_local_dashboard_port=0,
        ray_num_evaluators=1,
        ray_cpus_per_evaluator=1.0,
        ray_num_proposers=0,
        ray_gpus_per_proposer=1.0,
        proposer_buffer=1,
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
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=610,
        heuristic_explore=0.33,
    )


def _seed_one_done_trial(db: ExperimentDB, run_id: str, problem_hash: str, core: _DummyCore) -> None:
    x_done = [0.11, 0.81]
    params_done = core.u_to_params(x_done)
    res_done = db.reserve_trial(
        run_id=run_id,
        problem_hash=problem_hash,
        param_hash="portfolio_pool_fallback_seed_done",
        x_u=list(x_done),
        params=params_done,
    )
    db.mark_done(
        res_done.trial_id,
        y=[1.05, 2.05],
        g=[-0.08],
        metrics={"obj1": 1.05, "obj2": 2.05, "penalty_total": -0.08},
    )


def test_r31du_ray_portfolio_pool_failure_then_local_qnehvi_success_keeps_portfolio_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    q_calls = {"n": 0}
    h_calls = {"n": 0}
    rand_calls = {"n": 0}

    def fake_propose_qnehvi(**kwargs):  # noqa: ARG001
        q_calls["n"] += 1
        if q_calls["n"] == 1:
            raise RuntimeError("forced portfolio pool qnehvi failure once")
        return SimpleNamespace(
            X=np.asarray([[0.27, 0.57]], dtype=float),
            meta={"method": "portfolio_local_qnehvi_after_pool_fail", "source": "r31du_test"},
        )

    def fake_propose_heuristic(**kwargs):  # noqa: ARG001
        h_calls["n"] += 1
        raise AssertionError("heuristic must not be used when local qnehvi succeeds")

    def fake_propose_random(*, d, q, seed=0):  # noqa: ARG001
        rand_calls["n"] += 1
        q_i = max(1, int(q))
        d_i = max(1, int(d))
        X = np.full((q_i, d_i), 0.95, dtype=float)
        return SimpleNamespace(X=X)

    monkeypatch.setattr(coord, "propose_qnehvi", fake_propose_qnehvi)
    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)
    monkeypatch.setattr(coord, "propose_random", fake_propose_random)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_portfolio_pool_fail_then_local_qnehvi"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args()
    core = _DummyCore(dim=2)

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31du_qok", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31du_qok", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31du_qok",
            objective_keys=["obj1", "obj2"],
        )

    assert q_calls["n"] >= 2
    assert h_calls["n"] == 0
    assert rand_calls["n"] >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "portfolio"
    assert meta["effective_mode"] == "portfolio"
    assert meta["method"] == "portfolio_local_qnehvi_after_pool_fail"
    assert "fallback_reason" not in meta
    assert "RuntimeError" in str(meta.get("pool_fallback_error") or "")
    assert (run_dir / "export" / "trials.csv").exists()


def test_r31du_ray_portfolio_pool_failure_and_local_qnehvi_failure_fall_back_to_heuristic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    q_calls = {"n": 0}
    h_calls = {"n": 0}
    rand_calls = {"n": 0}

    def fake_propose_qnehvi(**kwargs):  # noqa: ARG001
        q_calls["n"] += 1
        raise RuntimeError("forced portfolio qnehvi failure in pool and local")

    def fake_propose_heuristic(**kwargs):
        h_calls["n"] += 1
        return SimpleNamespace(
            X=np.asarray([[0.29, 0.69]], dtype=float),
            meta={"method": "portfolio_heuristic_after_pool_fail", "source": "r31du_test"},
        )

    def fake_propose_random(*, d, q, seed=0):  # noqa: ARG001
        rand_calls["n"] += 1
        q_i = max(1, int(q))
        d_i = max(1, int(d))
        X = np.full((q_i, d_i), 0.96, dtype=float)
        return SimpleNamespace(X=X)

    monkeypatch.setattr(coord, "propose_qnehvi", fake_propose_qnehvi)
    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)
    monkeypatch.setattr(coord, "propose_random", fake_propose_random)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_portfolio_pool_fail_qfail_to_heur"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args()
    core = _DummyCore(dim=2)

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31du_qh", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31du_qh", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31du_qh",
            objective_keys=["obj1", "obj2"],
        )

    assert q_calls["n"] >= 2
    assert h_calls["n"] >= 1
    assert rand_calls["n"] >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "portfolio"
    assert meta["effective_mode"] == "heuristic"
    assert meta["fallback_reason"] == "qnehvi_failed"
    assert "RuntimeError" in str(meta.get("fallback_error") or "")
    assert "RuntimeError" in str(meta.get("pool_fallback_error") or "")
    assert meta["method"] == "portfolio_heuristic_after_pool_fail"
    assert (run_dir / "export" / "trials.csv").exists()


def test_r31du_ray_portfolio_pool_local_qnehvi_and_heuristic_fail_fall_back_to_random(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    q_calls = {"n": 0}
    h_calls = {"n": 0}
    rand_calls = {"n": 0}

    def fake_propose_qnehvi(**kwargs):  # noqa: ARG001
        q_calls["n"] += 1
        raise RuntimeError("forced portfolio qnehvi failure in pool/local")

    def fake_propose_heuristic(**kwargs):  # noqa: ARG001
        h_calls["n"] += 1
        raise ValueError("forced portfolio heuristic failure")

    def fake_propose_random(*, d, q, seed=0):  # noqa: ARG001
        rand_calls["n"] += 1
        q_i = max(1, int(q))
        d_i = max(1, int(d))
        X = np.full((q_i, d_i), 0.97, dtype=float)
        return SimpleNamespace(X=X)

    monkeypatch.setattr(coord, "propose_qnehvi", fake_propose_qnehvi)
    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)
    monkeypatch.setattr(coord, "propose_random", fake_propose_random)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_portfolio_pool_qh_fail_to_random"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args()
    core = _DummyCore(dim=2)

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31du_qhr", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31du_qhr", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31du_qhr",
            objective_keys=["obj1", "obj2"],
        )

    assert q_calls["n"] >= 2
    assert h_calls["n"] >= 1
    assert rand_calls["n"] >= 2

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "portfolio"
    assert meta["effective_mode"] == "random"
    assert meta["reason"] == "qnehvi_and_heuristic_failed"
    err = str(meta.get("fallback_error") or "")
    assert "RuntimeError" in err
    assert "ValueError" in err
    assert "RuntimeError" in str(meta.get("pool_fallback_error") or "")
    assert (run_dir / "export" / "trials.csv").exists()
