from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pneumo_solver_ui.atomic_write_retry import atomic_write_json_retry


def test_r31bp_atomic_write_json_retries_transient_windows_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "sp.json"
    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("sharing violation")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)

    ok = atomic_write_json_retry(
        target,
        {"status": "stage_running", "idx": 1},
        max_wait_sec=0.5,
        retry_sleep_sec=0.0,
        label="stage-progress",
    )

    assert ok is True
    assert calls["n"] == 3
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "stage_running"


def test_r31bp_atomic_write_json_returns_false_after_persistent_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "sp.json"

    def locked_replace(src: str, dst: str) -> None:
        raise PermissionError("sharing violation")

    monkeypatch.setattr(os, "replace", locked_replace)

    ok = atomic_write_json_retry(
        target,
        {"status": "stage_running"},
        max_wait_sec=0.0,
        retry_sleep_sec=0.0,
        label="stage-progress",
    )

    assert ok is False
    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_r31bp_stage_runner_and_worker_use_atomic_retry_writer() -> None:
    root = Path(__file__).resolve().parents[1]
    stage_src = (root / "pneumo_solver_ui" / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    worker_src = (root / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py").read_text(encoding="utf-8")
    assert "from pneumo_solver_ui.atomic_write_retry import atomic_write_json_retry" in stage_src
    assert "label=\"stage-progress\"" in stage_src
    assert "from pneumo_solver_ui.atomic_write_retry import atomic_write_json_retry" in worker_src
    assert "label=\"worker-progress\"" in worker_src
