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
        return {"CPU": 1.0, "GPU": 0.0}

    def get_gpu_ids() -> List[int]:
        return []

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


def test_r31di_ray_runner_uses_heuristic_proposer_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
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
            X=np.asarray([[0.15, 0.55]], dtype=float),
            meta={"method": "heuristic_mock", "source": "r31di_test"},
        )

    monkeypatch.setattr(coord, "propose_heuristic", fake_propose_heuristic)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_heuristic"
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
        budget=1,
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=16,
        min_feasible=0,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=913,
        heuristic_explore=0.27,
    )

    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31di", spec={}, meta={"source": "test"})
        coord._run_ray(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31di",
            objective_keys=["obj1", "obj2"],
        )

    assert calls, "heuristic proposer must be called at least once"
    call = calls[0]
    assert call["X_done_shape"] == (0, 2)
    assert call["Y_min_shape"] == (0, 2)
    assert call["penalty_is_none"] is True
    assert call["q"] == 1
    assert call["pool_size"] == 913
    assert abs(float(call["explore_weight"]) - 0.27) < 1e-12

    meta_path = run_dir / "last_proposer_meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["requested_mode"] == "heuristic"
    assert meta["effective_mode"] == "heuristic"
    assert meta["method"] == "heuristic_mock"

    run_spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert str(run_spec.get("proposer") or "") == "heuristic"
    assert int(run_spec.get("heuristic_pool_size") or 0) == 913
    assert abs(float(run_spec.get("heuristic_explore") or 0.0) - 0.27) < 1e-12

    assert (run_dir / "export" / "trials.csv").exists()
