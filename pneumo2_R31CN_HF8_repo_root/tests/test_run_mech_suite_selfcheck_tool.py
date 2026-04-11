from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd
import pneumo_solver_ui

from pneumo_solver_ui.tools import run_mech_suite_selfcheck as mod


def test_opt_worker_import_smoke() -> None:
    worker = importlib.import_module("pneumo_solver_ui.opt_worker_v3_margins_energy")
    assert hasattr(worker, "load_model")


def test_build_probe_enabled_suite_forces_disabled_rows_without_mutation() -> None:
    rows = [
        {"имя": "a", "включен": False},
        {"name": "b", "enabled": False},
    ]
    probe = mod._build_probe_enabled_suite(rows)
    assert len(probe) == 2
    assert all(bool(row["enabled"]) is True for row in probe)
    assert all(bool(row["включен"]) is True for row in probe)
    assert bool(rows[0]["включен"]) is False
    assert bool(rows[1]["enabled"]) is False


def test_eval_worker_metrics_uses_full_runner_when_record_full_requested() -> None:
    fake_worker = ModuleType("fake_worker")
    calls = []

    def _eval_candidate_once(*args, **kwargs):
        raise AssertionError("metrics-only runner should not be used in record_full mode")

    def _eval_candidate_once_full(model, params, test, dt, t_end, targets):
        calls.append((float(dt), float(t_end), dict(targets)))
        return {"mech_selfcheck_ok": 1}, ("full",)

    fake_worker.eval_candidate_once = _eval_candidate_once
    fake_worker.eval_candidate_once_full = _eval_candidate_once_full

    metrics = mod._eval_worker_metrics(
        fake_worker,
        object(),
        {},
        {"имя": "full_case"},
        dt=0.01,
        t_end=0.2,
        targets={"target_force": 1.0},
        record_full=True,
    )

    assert int(metrics["mech_selfcheck_ok"]) == 1
    assert calls == [(0.01, 0.2, {"target_force": 1.0})]


def test_main_runs_probe_suite_when_all_rows_disabled(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    base_path = tmp_path / "base.json"
    suite_path = tmp_path / "suite.json"
    model_path = tmp_path / "model.py"
    outdir = tmp_path / "out"

    base_path.write_text("{}", encoding="utf-8")
    suite_path.write_text(
        json.dumps(
            [
                {
                    "имя": "probe_case",
                    "включен": False,
                    "dt": 0.02,
                    "t_end": 0.4,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    model_path.write_text("# dummy model placeholder\n", encoding="utf-8")

    fake_worker = ModuleType("pneumo_solver_ui.opt_worker_v3_margins_energy")
    calls = []

    def _load_model(path: str):
        assert path == str(model_path)
        return object()

    def _eval_candidate_once(model, params, test, dt, t_end, targets):
        calls.append(
            {
                "name": test["имя"],
                "dt": float(dt),
                "t_end": float(t_end),
                "targets": dict(targets),
            }
        )
        return {
            "mech_selfcheck_ok": 1,
            "mech_selfcheck_msg": "OK",
            "mech_selfcheck_err_wheel_frame_m": 0.0,
        }

    fake_worker.load_model = _load_model
    fake_worker.eval_candidate_once = _eval_candidate_once

    monkeypatch.setitem(sys.modules, "pneumo_solver_ui.opt_worker_v3_margins_energy", fake_worker)
    monkeypatch.setattr(pneumo_solver_ui, "opt_worker_v3_margins_energy", fake_worker, raising=False)

    rc = mod.main(
        [
            "--base",
            str(base_path),
            "--suite",
            str(suite_path),
            "--model",
            str(model_path),
            "--outdir",
            str(outdir),
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "suite has no enabled rows" in captured.out
    assert "tests=1" in captured.out
    assert len(calls) == 1
    assert calls[0]["name"] == "probe_case"
    assert calls[0]["dt"] == 0.02
    assert calls[0]["t_end"] == 0.4

    df = pd.read_csv(outdir / "mech_selfcheck_report_latest.csv")
    assert len(df) == 1
    assert str(df.loc[0, "test"]) == "probe_case"
    assert int(df.loc[0, "ok"]) == 1
