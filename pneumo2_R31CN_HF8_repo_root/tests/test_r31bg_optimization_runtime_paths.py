from __future__ import annotations

from pathlib import Path, PureWindowsPath

import pandas as pd

from pneumo_solver_ui.optimization_progress_live import summarize_staged_progress
from pneumo_solver_ui.optimization_runtime_paths import (
    console_python_executable,
    stage_fs_name,
    stage_out_csv_name,
    stage_worker_progress_path,
    staged_progress_path,
)


def _write_csv(path: Path, rows: int) -> None:
    pd.DataFrame({"id": list(range(rows)), "v": list(range(rows))}).to_csv(path, index=False)


def test_r31bg_console_python_executable_prefers_python_exe(tmp_path: Path) -> None:
    scripts = tmp_path / "Scripts"
    scripts.mkdir(parents=True)
    pyw = scripts / "pythonw.exe"
    py = scripts / "python.exe"
    pyw.write_text("", encoding="utf-8")
    py.write_text("", encoding="utf-8")
    assert console_python_executable(pyw) == str(py)
    assert console_python_executable(py) == str(py)


def test_r31bg_short_stage_paths_stay_under_windows_path_budget() -> None:
    root = PureWindowsPath(
        r"C:\Users\Admin\Desktop\PneumoApp_v6_80_R176_R31BF_optimization_staged_progress_fix_2026-03-29"
    ) / PureWindowsPath(
        r"PneumoApp_v6_80_R176_R31BF_optimization_staged_progress_fix_2026-03-29"
    )
    workspace = root / "runs" / "ui_sessions" / "UI_20260329_091551" / "workspace"
    run_dir = workspace / "opt_runs" / "main" / "p_9d2c451b0a26"
    stage_dir = run_dir / stage_fs_name(0, "stage0_relevance")
    out_csv = stage_dir / stage_out_csv_name(0)
    progress = stage_worker_progress_path(Path(str(out_csv)))
    staged = staged_progress_path(Path(str(run_dir)))

    assert len(str(out_csv)) < 260
    assert len(str(progress)) < 260
    assert len(str(staged)) < 260
    assert stage_dir.name == "s0"
    assert out_csv.name == "o0.csv"


def test_r31bg_progress_summary_reads_short_stage_layout(tmp_path: Path) -> None:
    run_dir = tmp_path / "prob_x"
    stage0 = run_dir / "s0"
    stage0.mkdir(parents=True)
    stage0_csv = stage0 / "o0.csv"
    _write_csv(stage0_csv, 3)
    payload = {
        "status": "stage_running",
        "stage": "stage0_relevance",
        "idx": 0,
        "stage_total": 3,
        "worker_out_csv": str(stage0_csv),
        "worker_progress": {
            "статус": "seed_eval",
            "готово_кандидатов": 1,
            "готово_кандидатов_в_файле": 1,
        },
    }
    summary = summarize_staged_progress(payload, run_dir)
    assert summary["stage_rows_current"] == 3
    assert summary["total_rows_live"] == 3


def test_r31bg_source_uses_runtime_path_helpers() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui"
    src_ui = (root / "pneumo_ui_app.py").read_text(encoding="utf-8")
    src_stage = (root / "opt_stage_runner_v1.py").read_text(encoding="utf-8")
    assert "build_optimization_run_dir" in src_ui
    assert "staged_progress_path" in src_ui
    assert "console_python_executable" in src_ui
    assert "stage_fs_name" in src_stage
    assert "stage_out_csv_name" in src_stage
    assert "failed_worker_startup" in src_stage
