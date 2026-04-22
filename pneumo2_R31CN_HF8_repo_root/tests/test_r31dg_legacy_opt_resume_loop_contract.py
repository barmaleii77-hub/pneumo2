from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Tuple

import numpy as np

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
from pneumo_solver_ui.tools import run_dask_distributed_opt as dask_opt
from pneumo_solver_ui.tools import run_ray_distributed_opt as ray_opt

_RealExperimentDB = ExperimentDB


class _FakeEvaluator:
    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
        cfg_extra: Dict[str, Any] | None = None,
    ) -> None:
        self.model_py = model_py
        self.worker_py = worker_py
        self.base_json = base_json
        self.ranges_json = ranges_json
        self.suite_json = suite_json
        self.cfg_extra = dict(cfg_extra or {})
        self.base = {"name": "fake_resume"}
        self.ranges = {"x0": [0.0, 1.0], "x1": [0.0, 1.0]}
        self.suite = {"mode": "resume_test"}

    def dim(self) -> int:
        return 2

    def bounds_u(self) -> np.ndarray:
        return np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)

    def denormalize(self, x_u) -> Dict[str, float]:
        arr = np.asarray(x_u, dtype=float).reshape(-1)
        return {f"x{i}": float(v) for i, v in enumerate(arr.tolist())}

    def evaluate(self, trial_id: str, x_u, idx: int = 0) -> Dict[str, Any]:
        arr = np.asarray(x_u, dtype=float).reshape(-1)
        obj1 = float(np.sum(arr))
        obj2 = float(np.sum(arr * arr))
        return {
            "status": "done",
            "trial_id": str(trial_id),
            "obj1": obj1,
            "obj2": obj2,
            "penalty": 0.0,
            "metrics": {"idx": int(idx), "source": "resume_fake_eval"},
        }


class _FailingCoordinatorEvaluator:
    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
        cfg_extra: Dict[str, Any] | None = None,
    ) -> None:
        _ = (model_py, worker_py, base_json, ranges_json, suite_json, cfg_extra)
        raise RuntimeError("r31dg_forced_prestart_evaluator_init_error")


class _FailingRayActorEvaluator(_FakeEvaluator):
    _init_count = 0

    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
        cfg_extra: Dict[str, Any] | None = None,
    ) -> None:
        type(self)._init_count += 1
        # first init is coordinator-side evaluator; second init is first Ray actor
        if type(self)._init_count >= 2:
            raise RuntimeError("r31dg_forced_ray_actor_startup_error")
        super().__init__(
            model_py=model_py,
            worker_py=worker_py,
            base_json=base_json,
            ranges_json=ranges_json,
            suite_json=suite_json,
            cfg_extra=cfg_extra,
        )


def _fake_propose_next(**kwargs):
    x_hist = np.asarray(kwargs.get("X_u"), dtype=float)
    n_hist = int(x_hist.shape[0]) if x_hist.ndim == 2 else 0
    seed_val = 0.1 + 0.2 * n_hist
    x = np.asarray([seed_val, min(0.95, seed_val + 0.1)], dtype=float)
    return x, {"method": "resume_fake_propose", "n_hist": n_hist}


def _fake_propose_next_raises(**kwargs):
    _ = kwargs
    raise RuntimeError("r31dg_forced_runtime_propose_error")


class _FakeDaskFuture:
    def __init__(self, value: Any):
        self._value = value

    def result(self) -> Any:
        return self._value


class _FakeAsCompleted:
    def __init__(self, items: List[Any] | None = None, with_results: bool = False):
        self._items = list(items or [])
        self._with_results = bool(with_results)

    def add(self, item: Any) -> None:
        self._items.append(item)

    def __iter__(self):
        return self

    def __next__(self):
        if not self._items:
            raise StopIteration
        return self._items.pop(0)


class _FakeDaskClient:
    def __init__(self, address: str | None = None):
        self.address = address

    def scheduler_info(self) -> Dict[str, Any]:
        return {"nworkers": 1}

    def submit(self, fn, *args, **kwargs):
        _ = kwargs
        return _FakeDaskFuture(fn(*args))


class _FailingDaskClient:
    def __init__(self, address: str | None = None):
        _ = address
        raise RuntimeError("r31dg_forced_dask_client_init_error")


class _ZeroWorkerDaskClient(_FakeDaskClient):
    close_calls = 0

    def scheduler_info(self) -> Dict[str, Any]:
        return {"nworkers": 0}

    def close(self) -> None:
        type(self).close_calls += 1


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
    _state = {"shutdown_calls": 0}

    def init(*args, **kwargs):
        _ = args, kwargs
        return None

    def available_resources() -> Dict[str, float]:
        return {"CPU": 1.0}

    def get_gpu_ids() -> List[int]:
        return []

    def remote(*r_args, **r_kwargs):
        _ = r_kwargs

        def decorate(obj):
            if isinstance(obj, type):
                cls = obj

                class _RemoteClass:
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

    def wait(refs: List[_FakeRayRef], num_returns: int = 1, timeout: float | None = None) -> Tuple[List[_FakeRayRef], List[_FakeRayRef]]:
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

    def shutdown() -> None:
        _state["shutdown_calls"] += 1

    mod.init = init
    mod.remote = remote
    mod.wait = wait
    mod.get = get
    mod.shutdown = shutdown
    mod._state = _state
    mod.available_resources = available_resources
    mod.get_gpu_ids = get_gpu_ids
    return mod


class _RunRegistrySpy:
    def __init__(self) -> None:
        self.starts: List[Dict[str, Any]] = []
        self.ends: List[Dict[str, Any]] = []

    def env_context(self) -> Dict[str, Any]:
        return {"source": "r31dg_test"}

    def start_run(self, run_type: str, run_id: str, **fields: Any) -> str:
        self.starts.append({"run_type": str(run_type), "run_id": str(run_id), "fields": dict(fields)})
        return f"{run_type}|{run_id}|spy"

    def end_run(self, token: str, *, status: str = "done", **fields: Any) -> None:
        self.ends.append({"token": str(token), "status": str(status), "fields": dict(fields)})


class _TrackingExperimentDB:
    close_calls = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._inner = _RealExperimentDB(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def close(self) -> None:
        type(self).close_calls += 1
        self._inner.close()


def _prepare_model_files(tmp_path: Path) -> Tuple[Path, Path]:
    model = tmp_path / "model.py"
    worker = tmp_path / "worker.py"
    model.write_text("# fake model for resume\n", encoding="utf-8")
    worker.write_text("# fake worker for resume\n", encoding="utf-8")
    return model, worker


def _resolve_db_path(cfg: Dict[str, Any], run_dir: Path) -> Path:
    raw = str(cfg.get("db_path") or "").strip()
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = run_dir / p
        if p.exists():
            return p
    duck = run_dir / "experiments.duckdb"
    if duck.exists():
        return duck
    return run_dir / "experiments.sqlite"


def _start_delayed_stop_file(stop_file: Path, *, delay_sec: float = 0.6) -> None:
    def _writer() -> None:
        time.sleep(float(delay_sec))
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("stop\n", encoding="utf-8")

    t = threading.Thread(target=_writer, daemon=True)
    t.start()


def test_r31dg_ray_opt_resume_reuses_run_id_and_advances_budget(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_resume"

    fake_ray = _make_fake_ray_module()
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )
    rc_first = ray_opt.main()
    assert rc_first == 0

    run_cfg_path = out_dir / "run_config.json"
    first_cfg = json.loads(run_cfg_path.read_text(encoding="utf-8"))
    run_id = str(first_cfg.get("run_id") or "")
    assert run_id
    db_path = _resolve_db_path(first_cfg, out_dir)
    assert db_path.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--resume",
            "--budget",
            "2",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )
    rc_resume = ray_opt.main()
    assert rc_resume == 0

    resumed_cfg = json.loads(run_cfg_path.read_text(encoding="utf-8"))
    assert str(resumed_cfg.get("run_id") or "") == run_id

    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 2


def test_r31dg_dask_opt_resume_reuses_run_id_and_advances_budget(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_resume"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )
    rc_first = dask_opt.main()
    assert rc_first == 0

    run_cfg_path = out_dir / "run_config.json"
    first_cfg = json.loads(run_cfg_path.read_text(encoding="utf-8"))
    run_id = str(first_cfg.get("run_id") or "")
    assert run_id
    db_path = _resolve_db_path(first_cfg, out_dir)
    assert db_path.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--resume",
            "--budget",
            "2",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )
    rc_resume = dask_opt.main()
    assert rc_resume == 0

    resumed_cfg = json.loads(run_cfg_path.read_text(encoding="utf-8"))
    assert str(resumed_cfg.get("run_id") or "") == run_id

    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 2


def test_r31dg_dask_opt_queue_target_zero_is_sanitized_to_progress(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_queue_target_zero"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    _start_delayed_stop_file(out_dir / "STOP_DISTRIBUTED.txt", delay_sec=0.6)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "0",
            "--n-init",
            "1",
        ],
    )
    rc = dask_opt.main()
    assert rc == 0

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31dg_dask_opt_num_workers_zero_is_sanitized_to_progress(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_num_workers_zero"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "0",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )
    rc = dask_opt.main()
    assert rc == 0

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31dg_ray_opt_num_workers_zero_is_sanitized_to_progress(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_num_workers_zero"

    fake_ray = _make_fake_ray_module()
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "0",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )
    rc = ray_opt.main()
    assert rc == 0

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31dg_ray_opt_queue_target_zero_is_sanitized_to_progress(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_queue_target_zero"

    fake_ray = _make_fake_ray_module()
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "0",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )
    rc = ray_opt.main()
    assert rc == 0

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31dg_dask_opt_client_init_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_client_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FailingDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )

    rc = dask_opt.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask init failed:" in out_text
    assert "r31dg_forced_dask_client_init_error" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert "Dask init failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert _TrackingExperimentDB.close_calls == 1

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        assert "Dask init failed:" in str(meta.get("error") or "")


def test_r31dg_dask_opt_zero_workers_init_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_zero_workers_init_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _ZeroWorkerDaskClient.close_calls = 0
    fake_distributed.Client = _ZeroWorkerDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )

    rc = dask_opt.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask init failed:" in out_text
    assert "no Dask workers connected" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    end_err = str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert "Dask init failed:" in end_err
    assert "no Dask workers connected" in end_err
    assert _TrackingExperimentDB.close_calls == 1
    assert _ZeroWorkerDaskClient.close_calls == 1

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        err = str(meta.get("error") or "")
        assert "Dask init failed:" in err
        assert "no Dask workers connected" in err


def test_r31dg_ray_opt_init_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_init_fail"

    fake_ray = _make_fake_ray_module()

    def _failing_ray_init(*args, **kwargs):
        _ = args, kwargs
        raise RuntimeError("r31dg_forced_ray_init_error")

    fake_ray.init = _failing_ray_init

    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )

    rc = ray_opt.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray init failed:" in out_text
    assert "r31dg_forced_ray_init_error" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert "Ray init failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert _TrackingExperimentDB.close_calls == 1
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        assert "Ray init failed:" in str(meta.get("error") or "")


def test_r31dg_ray_opt_actor_startup_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_actor_startup_fail"

    fake_ray = _make_fake_ray_module()

    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    _FailingRayActorEvaluator._init_count = 0
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FailingRayActorEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )

    rc = ray_opt.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray evaluator actor startup failed:" in out_text
    assert "r31dg_forced_ray_actor_startup_error" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert "Ray evaluator actor startup failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert _TrackingExperimentDB.close_calls == 1
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        err = str(meta.get("error") or "")
        assert "Ray evaluator actor startup failed:" in err
        assert "r31dg_forced_ray_actor_startup_error" in err


def test_r31dg_dask_opt_runtime_propose_failure_returns_1_and_logs_fatal(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_runtime_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next_raises)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )

    rc = dask_opt.main()
    assert rc == 1
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    end_err = str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert "Dask runtime failed:" in end_err
    assert "r31dg_forced_runtime_propose_error" in end_err
    assert _TrackingExperimentDB.close_calls == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask runtime failed:" in out_text
    assert "r31dg_forced_runtime_propose_error" in out_text

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        err = str(meta.get("error") or "")
        assert "Dask runtime failed:" in err
        assert "r31dg_forced_runtime_propose_error" in err


def test_r31dg_ray_opt_runtime_propose_failure_returns_1_and_logs_fatal(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_runtime_fail"

    fake_ray = _make_fake_ray_module()
    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_mobo = __import__("pneumo_solver_ui.pneumo_dist.mobo_propose", fromlist=["propose_next"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    monkeypatch.setattr(fake_eval_core, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(fake_mobo, "propose_next", _fake_propose_next_raises)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )

    rc = ray_opt.main()
    assert rc == 1
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    end_err = str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert "Ray runtime failed:" in end_err
    assert "r31dg_forced_runtime_propose_error" in end_err
    assert _TrackingExperimentDB.close_calls == 1
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray runtime failed:" in out_text
    assert "r31dg_forced_runtime_propose_error" in out_text

    cfg = json.loads((out_dir / "run_config.json").read_text(encoding="utf-8"))
    run_id = str(cfg.get("run_id") or "")
    db_path = _resolve_db_path(cfg, out_dir)
    db_engine = "duckdb" if db_path.suffix.lower() == ".duckdb" else "sqlite"
    with ExperimentDB(db_path, engine=db_engine) as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status") or "") == "error"
        err = str(meta.get("error") or "")
        assert "Ray runtime failed:" in err
        assert "r31dg_forced_runtime_propose_error" in err


def test_r31dg_dask_opt_prestart_evaluator_init_failure_returns_1(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_prestart_eval_fail"

    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setattr(fake_eval_core, "Evaluator", _FailingCoordinatorEvaluator)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_opt.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
        ],
    )

    rc = dask_opt.main()
    assert rc == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0
    assert _TrackingExperimentDB.close_calls == 0
    assert not (out_dir / "run_config.json").exists()
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask pre-start setup failed:" in out_text
    assert "r31dg_forced_prestart_evaluator_init_error" in out_text


def test_r31dg_ray_opt_prestart_evaluator_init_failure_returns_1(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_prestart_eval_fail"

    fake_eval_core = __import__("pneumo_solver_ui.pneumo_dist.eval_core", fromlist=["Evaluator"])
    fake_expdb = __import__("pneumo_solver_ui.pneumo_dist.expdb", fromlist=["ExperimentDB"])
    import pneumo_solver_ui.run_registry as run_registry

    monkeypatch.setattr(fake_eval_core, "Evaluator", _FailingCoordinatorEvaluator)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(fake_expdb, "ExperimentDB", _TrackingExperimentDB)
    reg = _RunRegistrySpy()
    monkeypatch.setattr(run_registry, "start_run", reg.start_run)
    monkeypatch.setattr(run_registry, "end_run", reg.end_run)
    monkeypatch.setattr(run_registry, "env_context", reg.env_context)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_opt.py",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--budget",
            "1",
            "--num-workers",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--ray-address",
            "local",
        ],
    )

    rc = ray_opt.main()
    assert rc == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0
    assert _TrackingExperimentDB.close_calls == 0
    assert not (out_dir / "run_config.json").exists()
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray pre-start setup failed:" in out_text
    assert "r31dg_forced_prestart_evaluator_init_error" in out_text
