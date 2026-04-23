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
    calls: List[str] = []

    def __init__(
        self,
        model_path: str,
        worker_path: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
        cfg: Dict[str, Any] | None = None,
        problem_hash: str | None = None,
    ) -> None:
        _ = model_path, worker_path, base_json, ranges_json, suite_json, cfg, problem_hash

    def evaluate(self, trial_id: str, x_u: List[float]) -> Tuple[List[float], List[float], Dict[str, Any]]:
        _FakeEvaluatorCore.calls.append(str(trial_id))
        arr = np.asarray(x_u, dtype=float).reshape(-1)
        obj1 = float(arr[0]) if arr.size > 0 else 0.0
        obj2 = float(arr[1]) if arr.size > 1 else obj1
        y = [obj1, obj2]
        g = [0.0]
        row = {"trial_id": str(trial_id), "obj1": y[0], "obj2": y[1], "penalty_total": 0.0}
        return y, g, row


def _duplicate_random(*, d: int, q: int, seed: int = 0):  # noqa: ARG001
    q_i = max(1, int(q))
    d_i = max(1, int(d))
    return SimpleNamespace(X=np.full((q_i, d_i), 0.37, dtype=float))


def _make_duplicate_heuristic(calls: List[Dict[str, float]]):
    def _fake_propose_heuristic(**kwargs):
        calls.append(
            {
                "q": float(kwargs.get("q") or 0.0),
                "explore_weight": float(kwargs.get("explore_weight") or 0.0),
                "pool_size": float(kwargs.get("pool_size") or 0.0),
            }
        )
        q_i = max(1, int(kwargs.get("q") or 1))
        X_done = kwargs.get("X_done")
        dim = 1
        if isinstance(X_done, np.ndarray) and X_done.ndim == 2 and int(X_done.shape[1]) > 0:
            dim = int(X_done.shape[1])
        return SimpleNamespace(
            X=np.full((q_i, dim), 0.37, dtype=float),
            meta={"method": "heuristic_duplicate_capture"},
        )

    return _fake_propose_heuristic


def _make_duplicate_qnehvi():
    def _fake_propose_qnehvi(**kwargs):
        q_i = max(1, int(kwargs.get("q") or 1))
        X_done = kwargs.get("X_done")
        dim = 1
        if isinstance(X_done, np.ndarray) and X_done.ndim == 2 and int(X_done.shape[1]) > 0:
            dim = int(X_done.shape[1])
        return SimpleNamespace(
            X=np.full((q_i, dim), 0.37, dtype=float),
            meta={"method": "qnehvi_duplicate_capture"},
        )

    return _fake_propose_qnehvi


def _make_progressive_heuristic(calls: List[Dict[str, float]]):
    state = {"n": 0}

    def _fake_propose_heuristic(**kwargs):
        state["n"] += 1
        call_i = int(state["n"])
        calls.append(
            {
                "call": float(call_i),
                "q": float(kwargs.get("q") or 0.0),
                "explore_weight": float(kwargs.get("explore_weight") or 0.0),
                "pool_size": float(kwargs.get("pool_size") or 0.0),
            }
        )
        q_i = max(1, int(kwargs.get("q") or 1))
        X_done = kwargs.get("X_done")
        dim = 1
        if isinstance(X_done, np.ndarray) and X_done.ndim == 2 and int(X_done.shape[1]) > 0:
            dim = int(X_done.shape[1])
        base = min(0.95, 0.11 * float(call_i))
        return SimpleNamespace(
            X=np.full((q_i, dim), float(base), dtype=float),
            meta={"method": "heuristic_progressive_capture"},
        )

    return _fake_propose_heuristic


def _make_duplicate_random_capture(q_calls: List[int]):
    def _fake_propose_random(*, d: int, q: int, seed: int = 0):  # noqa: ARG001
        q_i = max(1, int(q))
        d_i = max(1, int(d))
        q_calls.append(int(q_i))
        return SimpleNamespace(X=np.full((q_i, d_i), 0.37, dtype=float))

    return _fake_propose_random


def _install_fake_distributed(monkeypatch, submit_log: List[str]) -> None:
    fake_distributed = ModuleType("distributed")

    class FakeFuture:
        def __init__(self, trial_id: str, x_u: list[float]) -> None:
            self._trial_id = str(trial_id)
            self._x = [float(v) for v in list(x_u)]

        def result(self):
            arr = np.asarray(self._x, dtype=float).reshape(-1)
            obj1 = float(arr[0]) if arr.size > 0 else 0.0
            obj2 = float(arr[1]) if arr.size > 1 else obj1
            y = [obj1, obj2]
            g = [0.0]
            row = {"trial_id": self._trial_id, "obj1": y[0], "obj2": y[1], "penalty_total": 0.0}
            return y, g, row

    class FakeLocalCluster:
        def __init__(self, **_kwargs) -> None:
            pass

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def scheduler_info(self) -> dict[str, object]:
            return {"workers": {"w0": {}}}

        def submit(self, _fn, trial_id, x_u, pure=False):  # noqa: ARG002
            submit_log.append(str(trial_id))
            return FakeFuture(str(trial_id), list(x_u))

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
        return {"CPU": 2.0, "GPU": 0.0}

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


def _base_dask_args(*, budget: int) -> SimpleNamespace:
    return SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        proposer="random",
        q=1,
        dask_scheduler="",
        dask_workers=1,
        dask_threads_per_worker=1,
        dask_memory_limit="",
        dask_dashboard_address="",
        max_inflight=2,
        seed=7,
        budget=int(budget),
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=0,
        min_feasible=0,
        proposer_buffer=2,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=256,
        heuristic_explore=0.7,
    )


def _base_ray_args(*, budget: int) -> SimpleNamespace:
    return SimpleNamespace(
        model="model.py",
        worker="worker.py",
        base_json="",
        ranges_json="",
        suite_json="",
        penalty_key="penalty_total",
        penalty_tol=0.0,
        proposer="random",
        q=1,
        ray_address="local",
        ray_runtime_env="off",
        ray_runtime_env_json="",
        ray_runtime_exclude=[],
        ray_local_num_cpus=0,
        ray_local_dashboard=False,
        ray_local_dashboard_port=0,
        ray_num_evaluators=2,
        ray_cpus_per_evaluator=1.0,
        ray_num_proposers=0,
        ray_gpus_per_proposer=1.0,
        proposer_buffer=2,
        max_inflight=2,
        seed=11,
        budget=int(budget),
        seed_json="",
        resume=False,
        stale_ttl_sec=600,
        hv_log=False,
        export_every=0,
        n_init=0,
        min_feasible=0,
        device="auto",
        botorch_no_normalize_objectives=False,
        botorch_ref_margin=0.1,
        botorch_num_restarts=10,
        botorch_raw_samples=512,
        botorch_maxiter=200,
        heuristic_pool_size=256,
        heuristic_explore=0.7,
    )


def _seed_one_done_trial(db: ExperimentDB, run_id: str, problem_hash: str, core: _DummyCore) -> None:
    x_done = [0.10, 0.90]
    params_done = core.u_to_params(x_done)
    res_done = db.reserve_trial(
        run_id=run_id,
        problem_hash=problem_hash,
        param_hash="r31ek_seed_done",
        x_u=list(x_done),
        params=params_done,
    )
    db.mark_done(
        res_done.trial_id,
        y=[1.0, 2.0],
        g=[-0.1],
        metrics={"obj1": 1.0, "obj2": 2.0, "penalty_total": -0.1},
    )


def test_r31ek_dask_skips_duplicate_running_trial_submission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    submit_log: List[str] = []
    _install_fake_distributed(monkeypatch, submit_log)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    monkeypatch.setattr(coord, "propose_random", _duplicate_random)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_duplicate_guard"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_dask_args(budget=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_dask", spec={}, meta={"source": "test"})
        coord._run_dask(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_dask",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    # Duplicate proposer output must not schedule the same trial twice.
    assert len(submit_log) == len(set(submit_log))
    # Anti-stall rescue should still drive progress to budget.
    assert len(done_rows) == 2
    assert len({tuple(float(v) for v in row.get("x_u", [])) for row in done_rows}) == 2

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert spec["backend"] == "dask"
    assert int(spec.get("stall_rescue_count") or 0) >= 1
    assert int(spec.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(spec.get("stall_terminated")) is False
    assert int(spec.get("dedup_skip_total") or 0) >= 1
    assert int(spec.get("dedup_skip_running_count") or 0) >= 1
    mode_counts = dict(spec.get("proposer_effective_mode_counts") or {})
    reason_counts = dict(spec.get("proposer_reason_counts") or {})
    assert int(mode_counts.get("random") or 0) >= 1
    assert int(spec.get("proposer_meta_events") or 0) >= 1
    assert len(reason_counts) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("stall_rescue_count") or 0) >= 1
    assert int(meta.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(meta.get("stall_terminated")) is False
    assert int(meta.get("dedup_skip_total") or 0) >= 1
    assert int(meta.get("dedup_skip_running_count") or 0) >= 1
    assert int(meta.get("dedup_skip_total") or 0) == int(spec.get("dedup_skip_total") or 0)


def test_r31ek_ray_skips_duplicate_running_trial_submission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    monkeypatch.setattr(coord, "propose_random", _duplicate_random)
    _FakeEvaluatorCore.calls = []

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_duplicate_guard"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_ray_args(budget=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_ray", spec={}, meta={"source": "test"})
        coord._run_ray(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_ray",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(_FakeEvaluatorCore.calls) == len(set(_FakeEvaluatorCore.calls))
    assert len(done_rows) == 2
    assert len({tuple(float(v) for v in row.get("x_u", [])) for row in done_rows}) == 2

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert spec["backend"] == "ray"
    assert int(spec.get("stall_rescue_count") or 0) >= 1
    assert int(spec.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(spec.get("stall_terminated")) is False
    assert int(spec.get("dedup_skip_total") or 0) >= 1
    assert int(spec.get("dedup_skip_running_count") or 0) >= 1
    mode_counts = dict(spec.get("proposer_effective_mode_counts") or {})
    reason_counts = dict(spec.get("proposer_reason_counts") or {})
    assert int(mode_counts.get("random") or 0) >= 1
    assert int(spec.get("proposer_meta_events") or 0) >= 1
    assert len(reason_counts) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("stall_rescue_count") or 0) >= 1
    assert int(meta.get("stall_rescue_limit_cycles") or 0) >= 8
    assert bool(meta.get("stall_terminated")) is False
    assert int(meta.get("dedup_skip_total") or 0) >= 1
    assert int(meta.get("dedup_skip_running_count") or 0) >= 1
    assert int(meta.get("dedup_skip_total") or 0) == int(spec.get("dedup_skip_total") or 0)


def test_r31ek_portfolio_primary_prefers_heuristic_from_recent_history() -> None:
    history = [
        {"mode": "qnehvi", "success": False},
        {"mode": "qnehvi", "success": False},
        {"mode": "qnehvi", "success": False},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": True},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
    )
    assert str(primary) == "heuristic"
    assert str(reason) == "recent_heuristic_outperforming"
    assert int(stats.get("qnehvi_attempts") or 0) == 3
    assert int(stats.get("qnehvi_successes") or 0) == 0
    assert int(stats.get("heuristic_attempts") or 0) == 3
    assert int(stats.get("heuristic_successes") or 0) == 3


def test_r31ek_portfolio_primary_sticky_keeps_heuristic_when_data_is_insufficient() -> None:
    history = [
        {"mode": "qnehvi", "success": False},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": True},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
        previous_choice="heuristic",
    )
    assert str(primary) == "heuristic"
    assert str(reason) == "sticky_previous_choice"
    assert int(stats.get("qnehvi_attempts") or 0) == 1
    assert int(stats.get("heuristic_attempts") or 0) == 2


def test_r31ek_portfolio_primary_hysteresis_keeps_heuristic_on_small_qnehvi_edge() -> None:
    history = [
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": False},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
        previous_choice="heuristic",
        switch_hysteresis_gap=0.10,
    )
    assert str(primary) == "heuristic"
    assert str(reason) == "sticky_hysteresis"
    assert int(stats.get("qnehvi_attempts") or 0) == 4
    assert int(stats.get("heuristic_attempts") or 0) == 4


def test_r31ek_portfolio_primary_hysteresis_allows_qnehvi_on_strong_edge() -> None:
    history = [
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
        previous_choice="heuristic",
        switch_hysteresis_gap=0.10,
    )
    assert str(primary) == "qnehvi"
    assert str(reason) == "recent_qnehvi_outperforming"
    assert int(stats.get("qnehvi_successes") or 0) == 4
    assert int(stats.get("heuristic_successes") or 0) == 1


def test_r31ek_portfolio_primary_cooldown_holds_switch_on_moderate_edge() -> None:
    history = [
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": False},
        {"mode": "heuristic", "success": True},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
        previous_choice="heuristic",
        switch_hysteresis_gap=0.10,
        switch_cooldown_ticks=2,
        cooldown_override_gap=0.35,
    )
    assert str(primary) == "heuristic"
    assert str(reason) == "cooldown_hold"
    assert int(stats.get("qnehvi_attempts") or 0) == 4
    assert int(stats.get("heuristic_attempts") or 0) == 4


def test_r31ek_portfolio_primary_cooldown_allows_switch_on_strong_edge() -> None:
    history = [
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "qnehvi", "success": True},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
        {"mode": "heuristic", "success": False},
    ]
    primary, reason, stats = coord._portfolio_choose_primary_mode(
        history,
        lookback=8,
        min_attempts_per_mode=3,
        min_success_gap=0.20,
        previous_choice="heuristic",
        switch_hysteresis_gap=0.10,
        switch_cooldown_ticks=2,
        cooldown_override_gap=0.35,
    )
    assert str(primary) == "qnehvi"
    assert str(reason) == "recent_qnehvi_outperforming"
    assert int(stats.get("qnehvi_successes") or 0) == 4
    assert int(stats.get("heuristic_successes") or 0) == 0


def test_r31ek_dask_heuristic_adaptive_explore_after_stall(
    tmp_path: Path,
    monkeypatch,
) -> None:
    submit_log: List[str] = []
    _install_fake_distributed(monkeypatch, submit_log)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    heuristic_calls: List[Dict[str, float]] = []
    monkeypatch.setattr(coord, "propose_heuristic", _make_duplicate_heuristic(heuristic_calls))

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_heuristic_adaptive"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_dask_args(budget=2)
    args.proposer = "heuristic"
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_dask_heuristic_adaptive", spec={}, meta={"source": "test"})
        coord._run_dask(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_dask_heuristic_adaptive",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(done_rows) == 2
    assert heuristic_calls
    base_q = int(args.q)
    base_explore = float(args.heuristic_explore)
    base_pool = int(args.heuristic_pool_size)
    base_buffer = int(args.proposer_buffer)
    assert any(int(v.get("q") or 0) > base_q for v in heuristic_calls)
    assert any(float(v.get("explore_weight") or 0.0) > base_explore + 1e-12 for v in heuristic_calls)
    assert any(int(v.get("pool_size") or 0) > base_pool for v in heuristic_calls)

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("heuristic_buffer_base") or 0) == base_buffer
    assert int(spec.get("heuristic_buffer_last_effective") or 0) >= base_buffer
    assert int(spec.get("heuristic_buffer_boost_events") or 0) >= 1
    assert int(spec.get("heuristic_q_base") or 0) == base_q
    assert int(spec.get("heuristic_q_last_effective") or 0) >= base_q
    assert int(spec.get("heuristic_q_boost_events") or 0) >= 1
    assert int(spec.get("heuristic_pool_size_base") or 0) == base_pool
    assert int(spec.get("heuristic_pool_size_last_effective") or 0) >= base_pool
    assert int(spec.get("heuristic_pool_size_boost_events") or 0) >= 1
    assert float(spec.get("heuristic_explore_base") or 0.0) == base_explore
    assert float(spec.get("heuristic_explore_last_effective") or 0.0) >= base_explore
    assert int(spec.get("heuristic_explore_boost_events") or 0) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("heuristic_buffer_base") or 0) == base_buffer
    assert int(meta.get("heuristic_buffer_last_effective") or 0) >= base_buffer
    assert int(meta.get("heuristic_buffer_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_buffer_effective") or 0) >= base_buffer
    assert int(meta.get("heuristic_q_base") or 0) == base_q
    assert int(meta.get("heuristic_q_last_effective") or 0) >= base_q
    assert int(meta.get("heuristic_q_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_q_effective") or 0) >= base_q
    assert int(meta.get("heuristic_pool_size_base") or 0) == base_pool
    assert int(meta.get("heuristic_pool_size_last_effective") or 0) >= base_pool
    assert int(meta.get("heuristic_pool_size_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_pool_size_effective") or 0) >= base_pool
    assert float(meta.get("heuristic_explore_base") or 0.0) == base_explore
    assert float(meta.get("heuristic_explore_last_effective") or 0.0) >= base_explore
    assert int(meta.get("heuristic_explore_boost_events") or 0) >= 1
    assert float(meta.get("heuristic_explore_effective") or 0.0) >= base_explore


def test_r31ek_ray_heuristic_adaptive_explore_after_stall(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    heuristic_calls: List[Dict[str, float]] = []
    monkeypatch.setattr(coord, "propose_heuristic", _make_duplicate_heuristic(heuristic_calls))
    _FakeEvaluatorCore.calls = []

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_heuristic_adaptive"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_ray_args(budget=2)
    args.proposer = "heuristic"
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_ray_heuristic_adaptive", spec={}, meta={"source": "test"})
        coord._run_ray(
            args,
            core_local=_DummyCore(dim=2),
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_ray_heuristic_adaptive",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(done_rows) == 2
    assert heuristic_calls
    base_q = int(args.q)
    base_explore = float(args.heuristic_explore)
    base_pool = int(args.heuristic_pool_size)
    base_buffer = int(args.proposer_buffer)
    assert any(int(v.get("q") or 0) > base_q for v in heuristic_calls)
    assert any(float(v.get("explore_weight") or 0.0) > base_explore + 1e-12 for v in heuristic_calls)
    assert any(int(v.get("pool_size") or 0) > base_pool for v in heuristic_calls)

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("heuristic_buffer_base") or 0) == base_buffer
    assert int(spec.get("heuristic_buffer_last_effective") or 0) >= base_buffer
    assert int(spec.get("heuristic_buffer_boost_events") or 0) >= 1
    assert int(spec.get("heuristic_q_base") or 0) == base_q
    assert int(spec.get("heuristic_q_last_effective") or 0) >= base_q
    assert int(spec.get("heuristic_q_boost_events") or 0) >= 1
    assert int(spec.get("heuristic_pool_size_base") or 0) == base_pool
    assert int(spec.get("heuristic_pool_size_last_effective") or 0) >= base_pool
    assert int(spec.get("heuristic_pool_size_boost_events") or 0) >= 1
    assert float(spec.get("heuristic_explore_base") or 0.0) == base_explore
    assert float(spec.get("heuristic_explore_last_effective") or 0.0) >= base_explore
    assert int(spec.get("heuristic_explore_boost_events") or 0) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("heuristic_buffer_base") or 0) == base_buffer
    assert int(meta.get("heuristic_buffer_last_effective") or 0) >= base_buffer
    assert int(meta.get("heuristic_buffer_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_buffer_effective") or 0) >= base_buffer
    assert int(meta.get("heuristic_q_base") or 0) == base_q
    assert int(meta.get("heuristic_q_last_effective") or 0) >= base_q
    assert int(meta.get("heuristic_q_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_q_effective") or 0) >= base_q
    assert int(meta.get("heuristic_pool_size_base") or 0) == base_pool
    assert int(meta.get("heuristic_pool_size_last_effective") or 0) >= base_pool
    assert int(meta.get("heuristic_pool_size_boost_events") or 0) >= 1
    assert int(meta.get("heuristic_pool_size_effective") or 0) >= base_pool
    assert float(meta.get("heuristic_explore_base") or 0.0) == base_explore
    assert float(meta.get("heuristic_explore_last_effective") or 0.0) >= base_explore
    assert int(meta.get("heuristic_explore_boost_events") or 0) >= 1
    assert float(meta.get("heuristic_explore_effective") or 0.0) >= base_explore


def test_r31ek_dask_portfolio_adaptive_rand_blend_after_stall(
    tmp_path: Path,
    monkeypatch,
) -> None:
    submit_log: List[str] = []
    _install_fake_distributed(monkeypatch, submit_log)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    monkeypatch.setattr(coord, "propose_qnehvi", _make_duplicate_qnehvi())
    rand_q_calls: List[int] = []
    monkeypatch.setattr(coord, "propose_random", _make_duplicate_random_capture(rand_q_calls))

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_portfolio_rand_adaptive"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_dask_args(budget=3)
    args.proposer = "portfolio"
    args.n_init = 1
    core = _DummyCore(dim=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_dask_portfolio_rand_adaptive", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31ek_dask_portfolio_rand_adaptive", core)
        coord._run_dask(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_dask_portfolio_rand_adaptive",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(done_rows) == 3
    assert rand_q_calls
    assert any(int(qv) > 1 for qv in rand_q_calls)

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("portfolio_rand_q_last_base") or 0) >= 1
    assert int(spec.get("portfolio_rand_q_last_effective") or 0) >= int(spec.get("portfolio_rand_q_last_base") or 0)
    assert int(spec.get("portfolio_rand_q_boost_events") or 0) >= 1
    assert str(spec.get("portfolio_primary_last_choice") or "") == "qnehvi"
    assert str(spec.get("portfolio_primary_last_reason") or "") in {"default_qnehvi", "recent_qnehvi_outperforming"}
    assert int(spec.get("portfolio_primary_switches") or 0) == 0
    assert int(spec.get("portfolio_primary_switch_cooldown_span") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_holds") or 0) >= 0
    choice_counts = dict(spec.get("portfolio_primary_choice_counts") or {})
    assert int(choice_counts.get("qnehvi") or 0) >= 1
    assert int(choice_counts.get("heuristic") or 0) == 0
    assert int(spec.get("portfolio_history_size") or 0) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("portfolio_rand_q_last_base") or 0) >= 1
    assert int(meta.get("portfolio_rand_q_last_effective") or 0) >= int(meta.get("portfolio_rand_q_last_base") or 0)
    assert int(meta.get("portfolio_rand_q_boost_events") or 0) >= 1
    assert str(meta.get("portfolio_primary_choice") or "") == "qnehvi"
    assert str(meta.get("portfolio_preference_reason") or "") in {"default_qnehvi", "recent_qnehvi_outperforming"}
    assert int(meta.get("portfolio_history_size") or 0) >= 1
    assert int(meta.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(meta.get("portfolio_primary_cooldown_holds") or 0) >= 0


def test_r31ek_ray_portfolio_adaptive_rand_blend_after_stall(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(coord, "EvaluatorCore", _FakeEvaluatorCore)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    monkeypatch.setattr(coord, "propose_qnehvi", _make_duplicate_qnehvi())
    rand_q_calls: List[int] = []
    monkeypatch.setattr(coord, "propose_random", _make_duplicate_random_capture(rand_q_calls))
    _FakeEvaluatorCore.calls = []

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_ray_portfolio_rand_adaptive"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_ray_args(budget=3)
    args.proposer = "portfolio"
    args.n_init = 1
    core = _DummyCore(dim=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_ray_portfolio_rand_adaptive", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31ek_ray_portfolio_rand_adaptive", core)
        coord._run_ray(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_ray_portfolio_rand_adaptive",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(done_rows) == 3
    assert rand_q_calls
    assert any(int(qv) > 1 for qv in rand_q_calls)

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert int(spec.get("portfolio_rand_q_last_base") or 0) >= 1
    assert int(spec.get("portfolio_rand_q_last_effective") or 0) >= int(spec.get("portfolio_rand_q_last_base") or 0)
    assert int(spec.get("portfolio_rand_q_boost_events") or 0) >= 1
    assert str(spec.get("portfolio_primary_last_choice") or "") == "qnehvi"
    assert str(spec.get("portfolio_primary_last_reason") or "") in {"default_qnehvi", "recent_qnehvi_outperforming"}
    assert int(spec.get("portfolio_primary_switches") or 0) == 0
    assert int(spec.get("portfolio_primary_switch_cooldown_span") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_holds") or 0) >= 0
    choice_counts = dict(spec.get("portfolio_primary_choice_counts") or {})
    assert int(choice_counts.get("qnehvi") or 0) >= 1
    assert int(choice_counts.get("heuristic") or 0) == 0
    assert int(spec.get("portfolio_history_size") or 0) >= 1

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert int(meta.get("portfolio_rand_q_last_base") or 0) >= 1
    assert int(meta.get("portfolio_rand_q_last_effective") or 0) >= int(meta.get("portfolio_rand_q_last_base") or 0)
    assert int(meta.get("portfolio_rand_q_boost_events") or 0) >= 1
    assert str(meta.get("portfolio_primary_choice") or "") == "qnehvi"
    assert str(meta.get("portfolio_preference_reason") or "") in {"default_qnehvi", "recent_qnehvi_outperforming"}
    assert int(meta.get("portfolio_history_size") or 0) >= 1
    assert int(meta.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(meta.get("portfolio_primary_cooldown_holds") or 0) >= 0


def test_r31ek_dask_portfolio_primary_switches_to_heuristic_after_qnehvi_failures(
    tmp_path: Path,
    monkeypatch,
) -> None:
    submit_log: List[str] = []
    _install_fake_distributed(monkeypatch, submit_log)
    monkeypatch.setattr(coord, "sample_lhs", lambda n, d, seed: np.zeros((0, int(d)), dtype=float))
    qnehvi_calls: List[int] = []

    def _always_fail_qnehvi(**_kwargs):
        qnehvi_calls.append(1)
        raise RuntimeError("forced_qnehvi_failure_for_contract")

    monkeypatch.setattr(coord, "propose_qnehvi", _always_fail_qnehvi)
    heuristic_calls: List[Dict[str, float]] = []
    monkeypatch.setattr(coord, "propose_heuristic", _make_progressive_heuristic(heuristic_calls))
    monkeypatch.setattr(
        coord,
        "_adaptive_portfolio_rand_q",
        lambda need, stagnation_cycles, rescue_limit_cycles: (0, 0),
    )

    rand_q_calls: List[int] = []

    def _propose_random_allow_zero(*, d: int, q: int, seed: int = 0):  # noqa: ARG001
        q_i = max(0, int(q))
        d_i = max(1, int(d))
        rand_q_calls.append(int(q_i))
        if q_i <= 0:
            return SimpleNamespace(X=np.zeros((0, d_i), dtype=float))
        val = min(0.99, 0.02 * float(len(rand_q_calls)))
        return SimpleNamespace(X=np.full((q_i, d_i), float(val), dtype=float))

    monkeypatch.setattr(coord, "propose_random", _propose_random_allow_zero)

    db_path = tmp_path / "experiments.sqlite"
    run_dir = tmp_path / "run_dask_portfolio_primary_switch"
    run_dir.mkdir(parents=True, exist_ok=True)

    args = _base_dask_args(budget=5)
    args.proposer = "portfolio"
    args.n_init = 1
    args.max_inflight = 1
    args.proposer_buffer = 1
    args.q = 1
    core = _DummyCore(dim=2)
    with ExperimentDB(db_path, engine="sqlite") as db:
        run_id = db.create_run(problem_hash="ph_r31ek_dask_portfolio_primary_switch", spec={}, meta={"source": "test"})
        _seed_one_done_trial(db, run_id, "ph_r31ek_dask_portfolio_primary_switch", core)
        coord._run_dask(
            args,
            core_local=core,
            db=db,
            run_id=run_id,
            run_dir=run_dir,
            problem_hash="ph_r31ek_dask_portfolio_primary_switch",
            objective_keys=["obj1", "obj2"],
        )
        done_rows = db.fetch_done_trials(run_id)

    assert len(done_rows) == 5
    assert len(qnehvi_calls) >= 3
    assert len(heuristic_calls) >= 4

    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    assert str(spec.get("portfolio_primary_last_choice") or "") == "heuristic"
    assert str(spec.get("portfolio_primary_last_reason") or "") in {"recent_heuristic_outperforming", "sticky_previous_choice"}
    assert int(spec.get("portfolio_primary_switches") or 0) >= 1
    assert int(spec.get("portfolio_primary_switch_cooldown_span") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(spec.get("portfolio_primary_cooldown_holds") or 0) >= 0
    choice_counts = dict(spec.get("portfolio_primary_choice_counts") or {})
    assert int(choice_counts.get("qnehvi") or 0) >= 1
    assert int(choice_counts.get("heuristic") or 0) >= 1
    assert int(spec.get("portfolio_history_size") or 0) >= 6

    meta = json.loads((run_dir / "last_proposer_meta.json").read_text(encoding="utf-8"))
    assert str(meta.get("portfolio_primary_choice") or "") == "heuristic"
    assert str(meta.get("portfolio_preference_reason") or "") in {"recent_heuristic_outperforming", "sticky_previous_choice"}
    assert str(meta.get("effective_mode") or "") == "heuristic"
    assert int(meta.get("portfolio_history_size") or 0) >= 6
    assert int(meta.get("portfolio_primary_cooldown_ticks") or 0) >= 0
    assert int(meta.get("portfolio_primary_cooldown_holds") or 0) >= 0
