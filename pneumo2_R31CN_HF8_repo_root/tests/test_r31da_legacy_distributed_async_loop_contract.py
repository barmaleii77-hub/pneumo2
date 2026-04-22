from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Tuple

import numpy as np

from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
from pneumo_solver_ui.tools import run_dask_distributed_async as dask_async
from pneumo_solver_ui.tools import run_ray_distributed_async as ray_async

_RealExperimentDB = ExperimentDB


class _FakeEvaluator:
    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
    ) -> None:
        self.model_py = model_py
        self.worker_py = worker_py
        self.base_json = base_json
        self.ranges_json = ranges_json
        self.suite_json = suite_json
        self.base = {"name": "fake"}
        self.ranges = {"x0": [0.0, 1.0], "x1": [0.0, 1.0]}
        self.suite = {"mode": "test"}

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
            "metrics": {"idx": int(idx), "source": "fake_eval"},
        }


class _FailingRayActorEvaluator(_FakeEvaluator):
    _init_count = 0

    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
    ) -> None:
        type(self)._init_count += 1
        # First init is coordinator-side ev0; second init is first Ray evaluator actor.
        if type(self)._init_count >= 2:
            raise RuntimeError("r31da_forced_ray_actor_startup_error")
        super().__init__(
            model_py=model_py,
            worker_py=worker_py,
            base_json=base_json,
            ranges_json=ranges_json,
            suite_json=suite_json,
        )


class _FailingCoordinatorEvaluator:
    def __init__(
        self,
        model_py: str,
        worker_py: str,
        base_json: str | None = None,
        ranges_json: str | None = None,
        suite_json: str | None = None,
    ) -> None:
        _ = (model_py, worker_py, base_json, ranges_json, suite_json)
        raise RuntimeError("r31da_forced_coordinator_evaluator_init_error")


def _fake_propose_next(**kwargs):
    bounds = np.asarray(kwargs.get("bounds"), dtype=float)
    d = int(bounds.shape[1]) if bounds.ndim == 2 else 2
    x = np.full((d,), 0.25, dtype=float)
    return x, {"method": "fake_propose"}


def _fake_propose_next_progressive(**kwargs):
    x_hist = np.asarray(kwargs.get("X_u"), dtype=float)
    n_hist = int(x_hist.shape[0]) if x_hist.ndim == 2 else 0
    seed_val = 0.1 + 0.2 * n_hist
    x = np.asarray([seed_val, min(0.95, seed_val + 0.1)], dtype=float)
    return x, {"method": "fake_propose_progressive", "n_hist": n_hist}


def _fake_propose_next_raises(**kwargs):
    _ = kwargs
    raise RuntimeError("r31da_forced_propose_error")


def _fake_propose_next_interrupts(**kwargs):
    _ = kwargs
    raise KeyboardInterrupt()


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
    close_calls = 0

    def __init__(self, address: str | None = None):
        self.address = address

    def scheduler_info(self) -> Dict[str, Any]:
        return {"nworkers": 1}

    def submit(self, fn, *args, **kwargs):
        _ = kwargs
        return _FakeDaskFuture(fn(*args))

    def close(self) -> None:
        type(self).close_calls += 1


class _FailingDaskClient:
    def __init__(self, address: str | None = None):
        _ = address
        raise RuntimeError("r31da_forced_dask_client_init_error")


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


def _prepare_model_files(tmp_path: Path) -> Tuple[Path, Path]:
    model = tmp_path / "model.py"
    worker = tmp_path / "worker.py"
    model.write_text("# fake model\n", encoding="utf-8")
    worker.write_text("# fake worker\n", encoding="utf-8")
    return model, worker


class _RunRegistrySpy:
    def __init__(self) -> None:
        self.starts: List[Dict[str, Any]] = []
        self.ends: List[Dict[str, Any]] = []

    def env_context(self) -> Dict[str, Any]:
        return {"source": "r31da_test"}

    def start_run(self, run_type: str, run_id: str, **fields: Any) -> str:
        self.starts.append(
            {
                "run_type": str(run_type),
                "run_id": str(run_id),
                "fields": dict(fields),
            }
        )
        return f"{run_type}|{run_id}|spy"

    def end_run(self, token: str, *, status: str = "done", rc: int | None = None, **fields: Any) -> None:
        self.ends.append(
            {
                "token": str(token),
                "status": str(status),
                "rc": rc,
                "fields": dict(fields),
            }
        )


class _TrackingExperimentDB:
    close_calls = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._inner = _RealExperimentDB(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def close(self) -> None:
        type(self).close_calls += 1
        self._inner.close()


def test_r31da_dask_async_main_completes_one_trial_with_fake_cluster(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _FakeDaskClient.close_calls = 0
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    dask_async.main()

    assert (out_dir / "run_config.json").exists()
    assert (out_dir / "progress.json").exists()
    assert (out_dir / "progress_final.json").exists()
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.starts[0]["run_type"] == "dist_dask_async_opt"
    assert reg.starts[0]["run_id"] == run_id
    assert reg.ends[0]["token"] == f"dist_dask_async_opt|{run_id}|spy"
    assert reg.ends[0]["status"] == "done"
    assert reg.ends[0]["rc"] == 0
    assert _FakeDaskClient.close_calls == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31da_ray_async_main_completes_one_trial_with_fake_cluster(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async"

    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    ray_async.main()

    assert (out_dir / "run_config.json").exists()
    assert (out_dir / "progress.json").exists()
    assert (out_dir / "progress_final.json").exists()
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.starts[0]["run_type"] == "dist_ray_async_opt"
    assert reg.starts[0]["run_id"] == run_id
    assert reg.ends[0]["token"] == f"dist_ray_async_opt|{run_id}|spy"
    assert reg.ends[0]["status"] == "done"
    assert reg.ends[0]["rc"] == 0
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 1


def test_r31da_dask_async_resume_uses_run_config_defaults(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_resume"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_resume"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _FakeDaskClient.close_calls = 0
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )
    dask_async.main()

    cfg_path = out_dir / "run_config.json"
    first_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert str(first_cfg.get("run_id") or "") == run_id
    assert str(first_cfg.get("db_path") or "").endswith("experiments.sqlite")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
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
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )
    dask_async.main()

    resumed_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert str(resumed_cfg.get("run_id") or "") == run_id
    assert str(resumed_cfg.get("db_path") or "").endswith("experiments.sqlite")
    assert _FakeDaskClient.close_calls == 2
    assert _TrackingExperimentDB.close_calls == 2

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 2


def test_r31da_ray_async_resume_uses_run_config_defaults(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_resume"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_resume"

    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )
    ray_async.main()

    cfg_path = out_dir / "run_config.json"
    first_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert str(first_cfg.get("run_id") or "") == run_id
    assert str(first_cfg.get("db_path") or "").endswith("experiments.sqlite")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--resume",
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )
    ray_async.main()

    resumed_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert str(resumed_cfg.get("run_id") or "") == run_id
    assert str(resumed_cfg.get("db_path") or "").endswith("experiments.sqlite")
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 2
    assert _TrackingExperimentDB.close_calls == 2

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        assert str((run.get("meta") or {}).get("status")) == "done"
        counts = db.count_status(run_id)
        assert int(counts.get("done", 0) + counts.get("cached", 0)) >= 2


def test_r31da_dask_async_unexpected_error_marks_registry_and_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_error"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_error"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _FakeDaskClient.close_calls = 0
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_raises)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = dask_async.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask runtime failed:" in out_text
    assert "r31da_forced_propose_error" in out_text

    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.starts[0]["run_type"] == "dist_dask_async_opt"
    assert reg.starts[0]["run_id"] == run_id
    assert reg.ends[0]["token"] == f"dist_dask_async_opt|{run_id}|spy"
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    assert "Dask runtime failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert _FakeDaskClient.close_calls == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        assert "Dask runtime failed:" in str(meta.get("error") or "")
        assert "r31da_forced_propose_error" in str(meta.get("error") or "")


def test_r31da_ray_async_unexpected_error_marks_registry_and_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_error"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_error"

    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_raises)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = ray_async.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray runtime failed:" in out_text
    assert "r31da_forced_propose_error" in out_text

    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.starts[0]["run_type"] == "dist_ray_async_opt"
    assert reg.starts[0]["run_id"] == run_id
    assert reg.ends[0]["token"] == f"dist_ray_async_opt|{run_id}|spy"
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    assert "Ray runtime failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        assert "Ray runtime failed:" in str(meta.get("error") or "")
        assert "r31da_forced_propose_error" in str(meta.get("error") or "")


def test_r31da_dask_async_keyboard_interrupt_returns_130_and_marks_stopped(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_interrupt"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_interrupt"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _FakeDaskClient.close_calls = 0
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_interrupts)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = dask_async.main()
    assert rc == 130
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "stopped"
    assert reg.ends[0]["rc"] == 130
    assert _FakeDaskClient.close_calls == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "interrupted"


def test_r31da_ray_async_keyboard_interrupt_returns_130_and_marks_stopped(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_interrupt"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_interrupt"

    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_interrupts)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = ray_async.main()
    assert rc == 130
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "stopped"
    assert reg.ends[0]["rc"] == 130
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "interrupted"


def test_r31da_dask_async_client_init_failure_returns_1_and_marks_error(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_client_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_client_init_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FailingDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = dask_async.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask init failed:" in out_text
    assert "r31da_forced_dask_client_init_error" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    assert "Dask init failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        assert "Dask init failed:" in str(meta.get("error") or "")
        assert "r31da_forced_dask_client_init_error" in str(meta.get("error") or "")


def test_r31da_dask_async_zero_workers_init_failure_returns_1_and_marks_error(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_zero_workers_init_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_zero_workers_init_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    _ZeroWorkerDaskClient.close_calls = 0
    fake_distributed.Client = _ZeroWorkerDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = dask_async.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask init failed:" in out_text
    assert "no Dask workers connected" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    end_err = str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert "Dask init failed:" in end_err
    assert "no Dask workers connected" in end_err
    assert _ZeroWorkerDaskClient.close_calls == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        err = str(meta.get("error") or "")
        assert "Dask init failed:" in err
        assert "no Dask workers connected" in err


def test_r31da_ray_async_init_failure_returns_1_and_marks_error(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_init_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_init_fail"

    fake_ray = _make_fake_ray_module()

    def _failing_init(*args, **kwargs):
        _ = args, kwargs
        raise RuntimeError("r31da_forced_ray_init_error")

    fake_ray.init = _failing_init
    monkeypatch.setitem(sys.modules, "ray", fake_ray)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = ray_async.main()
    assert rc == 1
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray init failed:" in out_text
    assert "r31da_forced_ray_init_error" in out_text
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    assert "Ray init failed:" in str((reg.ends[0]["fields"] or {}).get("error") or "")
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        assert "Ray init failed:" in str(meta.get("error") or "")
        assert "r31da_forced_ray_init_error" in str(meta.get("error") or "")


def test_r31da_ray_async_actor_startup_failure_returns_1_and_marks_error(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_actor_startup_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_actor_startup_fail"

    fake_ray = _make_fake_ray_module()
    monkeypatch.setitem(sys.modules, "ray", fake_ray)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    _FailingRayActorEvaluator._init_count = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FailingRayActorEvaluator)
    monkeypatch.setattr(ray_async, "propose_next", _fake_propose_next_progressive)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
            "--queue-target",
            "1",
            "--n-init",
            "1",
            "--progress-every",
            "1",
        ],
    )

    rc = ray_async.main()
    assert rc == 1
    assert len(reg.starts) == 1
    assert len(reg.ends) == 1
    assert reg.ends[0]["status"] == "error"
    assert reg.ends[0]["rc"] == 1
    assert int(fake_ray._state.get("shutdown_calls") or 0) == 1
    assert _TrackingExperimentDB.close_calls == 1

    with ExperimentDB(db_path, engine="sqlite") as db:
        run = db.get_run(run_id)
        assert run is not None
        meta = dict(run.get("meta") or {})
        assert str(meta.get("status")) == "error"
        assert "r31da_forced_ray_actor_startup_error" in str(meta.get("error") or "")


def test_r31da_dask_async_resume_missing_run_closes_db_before_system_exit(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_resume_missing_run"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_resume_missing_run"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--resume",
            "--budget",
            "1",
        ],
    )

    try:
        dask_async.main()
        assert False, "Expected SystemExit for missing resume run"
    except SystemExit as e:
        assert "Run not found in DB" in str(e)
    assert _TrackingExperimentDB.close_calls == 1


def test_r31da_ray_async_resume_missing_run_closes_db_before_system_exit(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_resume_missing_run"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_resume_missing_run"

    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--resume",
            "--budget",
            "1",
        ],
    )

    try:
        ray_async.main()
        assert False, "Expected SystemExit for missing resume run"
    except SystemExit as e:
        assert "Run not found in DB" in str(e)
    assert _TrackingExperimentDB.close_calls == 1


def test_r31da_dask_async_resume_problem_hash_mismatch_closes_db_before_system_exit(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_resume_hash_mismatch"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_resume_hash_mismatch"
    out_dir.mkdir(parents=True, exist_ok=True)

    with ExperimentDB(db_path, engine="sqlite") as db:
        db.add_run(run_id, problem_hash="r31da_mismatched_problem_hash", meta={"seeded": True}, status="running")

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--resume",
            "--budget",
            "1",
        ],
    )

    try:
        dask_async.main()
        assert False, "Expected SystemExit for resume problem-hash mismatch"
    except SystemExit as e:
        assert "Problem hash mismatch for resume" in str(e)
    assert _TrackingExperimentDB.close_calls == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0


def test_r31da_ray_async_resume_problem_hash_mismatch_closes_db_before_system_exit(tmp_path: Path, monkeypatch) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_resume_hash_mismatch"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_resume_hash_mismatch"
    out_dir.mkdir(parents=True, exist_ok=True)

    with ExperimentDB(db_path, engine="sqlite") as db:
        db.add_run(run_id, problem_hash="r31da_mismatched_problem_hash", meta={"seeded": True}, status="running")

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FakeEvaluator)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--resume",
            "--budget",
            "1",
        ],
    )

    try:
        ray_async.main()
        assert False, "Expected SystemExit for resume problem-hash mismatch"
    except SystemExit as e:
        assert "Problem hash mismatch for resume" in str(e)
    assert _TrackingExperimentDB.close_calls == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0


def test_r31da_dask_async_prestart_evaluator_init_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_dask_prestart_eval_init_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_dask_async_prestart_eval_init_fail"

    fake_dask = ModuleType("dask")
    fake_distributed = ModuleType("dask.distributed")
    fake_distributed.Client = _FakeDaskClient
    fake_distributed.as_completed = lambda items, with_results=False: _FakeAsCompleted(items, with_results=with_results)
    monkeypatch.setitem(sys.modules, "dask", fake_dask)
    monkeypatch.setitem(sys.modules, "dask.distributed", fake_distributed)

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(dask_async, "Evaluator", _FailingCoordinatorEvaluator)
    monkeypatch.setattr(dask_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(dask_async, "start_run", reg.start_run)
    monkeypatch.setattr(dask_async, "end_run", reg.end_run)
    monkeypatch.setattr(dask_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_dask_distributed_async.py",
            "--scheduler",
            "tcp://fake:8786",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
        ],
    )

    rc = dask_async.main()
    assert rc == 1
    assert _TrackingExperimentDB.close_calls == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Dask pre-start setup failed:" in out_text
    assert "r31da_forced_coordinator_evaluator_init_error" in out_text

    with ExperimentDB(db_path, engine="sqlite") as db:
        assert db.get_run(run_id) is None


def test_r31da_ray_async_prestart_evaluator_init_failure_returns_1_and_closes_db(tmp_path: Path, monkeypatch, capsys) -> None:
    model, worker = _prepare_model_files(tmp_path)
    out_dir = tmp_path / "out_ray_prestart_eval_init_fail"
    db_path = out_dir / "experiments.sqlite"
    run_id = "r31da_ray_async_prestart_eval_init_fail"

    reg = _RunRegistrySpy()
    _TrackingExperimentDB.close_calls = 0
    monkeypatch.setattr(ray_async, "Evaluator", _FailingCoordinatorEvaluator)
    monkeypatch.setattr(ray_async, "ExperimentDB", _TrackingExperimentDB)
    monkeypatch.setattr(ray_async, "start_run", reg.start_run)
    monkeypatch.setattr(ray_async, "end_run", reg.end_run)
    monkeypatch.setattr(ray_async, "env_context", reg.env_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ray_distributed_async.py",
            "--address",
            "local",
            "--model",
            str(model),
            "--worker",
            str(worker),
            "--out-dir",
            str(out_dir),
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--budget",
            "1",
        ],
    )

    rc = ray_async.main()
    assert rc == 1
    assert _TrackingExperimentDB.close_calls == 1
    assert len(reg.starts) == 0
    assert len(reg.ends) == 0
    captured = capsys.readouterr()
    out_text = str(captured.out or "")
    assert "FATAL: Ray pre-start setup failed:" in out_text
    assert "r31da_forced_coordinator_evaluator_init_error" in out_text

    with ExperimentDB(db_path, engine="sqlite") as db:
        assert db.get_run(run_id) is None
