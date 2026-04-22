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


def _make_fake_ray_module(*, gpu: float) -> ModuleType:
    mod = ModuleType("ray")

    def init(*args, **kwargs):
        _ = args, kwargs
        return None

    def cluster_resources() -> Dict[str, float]:
        return {"CPU": 1.0, "GPU": float(gpu)}

    def get_gpu_ids() -> List[int]:
        return [0] if gpu > 0 else []

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


def _seed_one_done_trial(db: ExperimentDB, run_id: str, problem_hash: str, core: _DummyCore) -> None:
    x_done = [0.18, 0.88]
    params_done = core.u_to_params(x_done)
    res_done = db.reserve_trial(
        run_id=run_id,
        problem_hash=problem_hash,
        param_hash=f"{problem_hash}_seed_done",
        x_u=list(x_done),
        params=params_done,
    )
    db.mark_done(
        res_done.trial_id,
        y=[1.0, 2.0],
        g=[-0.05],
        metrics={"obj1": 1.0, "obj2": 2.0, "penalty_total": -0.05},
    )


def _base_args(*, gpp: float) -> SimpleNamespace:
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
        ray_address="local",
        ray_runtime_env="off",
        ray_runtime_env_json="",
        ray_runtime_exclude=[],
        ray_local_num_cpus=0,
        ray_local_dashboard=False,
        ray_local_dashboard_port=0,
        ray_num_evaluators=1,
        ray_cpus_per_evaluator=1.0,
        ray_num_proposers=4,
        ray_gpus_per_proposer=float(gpp),
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
        heuristic_pool_size=780,
        heuristic_explore=0.35,
    )


def test_r31ej_run_spec_reports_gpu_capped_pool_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module(gpu=1.0)
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    monkeypatch.setattr(
        coord,
        "propose_qnehvi",
        lambda **kwargs: SimpleNamespace(
            X=np.asarray([[0.40, 0.70]], dtype=float),
            meta={"method": "qnehvi_for_run_spec", "source": "r31ej_test"},
        ),
    )

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_pool_gpu_capped_spec"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args(gpp=1.0)
    core = _DummyCore(dim=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ej_cap", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31ej_cap", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ej_cap",
            objective_keys=["obj1", "obj2"],
        )

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("ray_num_proposers_requested") or 0) == 4
    assert int(spec.get("ray_num_proposers") or 0) == 1
    assert bool(spec.get("ray_proposer_pool_enabled")) is True
    assert spec.get("ray_proposer_pool_disabled_reason") is None
    assert int(spec.get("stall_rescue_count") or 0) == 0
    assert int(spec.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(spec.get("stall_terminated")) is False
    assert int(spec.get("dedup_skip_total") or 0) == 0
    mode_counts = dict(spec.get("proposer_effective_mode_counts") or {})
    assert int(mode_counts.get("qnehvi") or 0) >= 1
    assert int(spec.get("proposer_meta_events") or 0) >= 1


def test_r31ej_run_spec_reports_gpu_budget_insufficient_when_pool_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module(gpu=1.0)
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))

    monkeypatch.setattr(
        coord,
        "propose_qnehvi",
        lambda **kwargs: SimpleNamespace(
            X=np.asarray([[0.41, 0.71]], dtype=float),
            meta={"method": "qnehvi_local_for_run_spec", "source": "r31ej_test"},
        ),
    )

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_pool_gpu_insufficient_spec"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args(gpp=2.0)
    core = _DummyCore(dim=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ej_insuff", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31ej_insuff", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ej_insuff",
            objective_keys=["obj1", "obj2"],
        )

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("ray_num_proposers_requested") or 0) == 4
    assert int(spec.get("ray_num_proposers") or 0) == 0
    assert bool(spec.get("ray_proposer_pool_enabled")) is False
    assert str(spec.get("ray_proposer_pool_disabled_reason") or "") == "gpu_budget_insufficient"
    assert int(spec.get("stall_rescue_count") or 0) == 0
    assert int(spec.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(spec.get("stall_terminated")) is False
    assert int(spec.get("dedup_skip_total") or 0) == 0
    mode_counts = dict(spec.get("proposer_effective_mode_counts") or {})
    assert int(mode_counts.get("qnehvi") or 0) >= 1
    assert int(spec.get("proposer_meta_events") or 0) >= 1
