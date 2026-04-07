from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.optimization_progress_live import summarize_staged_progress
from pneumo_solver_ui.opt_stage_runner_v1 import estimate_stage_seed_cap


def _write_csv(path: Path, rows: int) -> None:
    df = pd.DataFrame({"id": list(range(rows)), "v": list(range(rows))})
    df.to_csv(path, index=False)


def test_r31bf_summarize_staged_progress_derives_live_rows_from_stage_csvs(tmp_path: Path) -> None:
    run_dir = tmp_path / "prob_x"
    stage0 = run_dir / "stage0_relevance"
    stage1 = run_dir / "stage1_long"
    stage0.mkdir(parents=True)
    stage1.mkdir(parents=True)

    stage0_csv = stage0 / "stage_00.csv"
    stage1_csv = stage1 / "stage_01.csv"
    _write_csv(stage0_csv, 25)
    _write_csv(stage1_csv, 2)

    # Simulate stale nested worker progress: zero rows even though current CSV already has rows.
    wp = {
        "статус": "baseline_eval",
        "ts_last_write": float(stage1_csv.stat().st_mtime - 60.0),
        "готово_кандидатов": 0,
        "готово_кандидатов_в_файле": 0,
    }
    payload = {
        "status": "stage_running",
        "stage": "stage1_long",
        "idx": 1,
        "stage_total": 3,
        "worker_out_csv": str(stage1_csv),
        "worker_progress": wp,
        "stage_budget_sec": 198.0,
        "stage_elapsed_sec": 42.0,
    }

    summary = summarize_staged_progress(payload, run_dir)
    assert summary["stage"] == "stage1_long"
    assert summary["stage_rows_current"] == 2
    assert summary["stage_rows_done_before"] == 25
    assert summary["total_rows_live"] == 27
    assert summary["worker_done_current"] == 2
    assert summary["worker_written_current"] == 2
    assert summary["worker_progress_stale"] is True


def test_r31bf_estimate_stage_seed_cap_respects_budget_of_heavier_next_stage(tmp_path: Path) -> None:
    run_dir = tmp_path / "prob_x"
    stage0 = run_dir / "stage0_relevance"
    stage1 = run_dir / "stage1_long"
    stage0.mkdir(parents=True)
    stage1.mkdir(parents=True)

    prev_csv = stage0 / "stage_00.csv"
    _write_csv(prev_csv, 25)
    prev_prog = stage0 / "stage_00_progress.json"
    prev_prog.write_text(json.dumps({"прошло_сек": 139.84}, ensure_ascii=False), encoding="utf-8")

    stage_plan = [
        {"name": "stage0_relevance", "minutes": 2.2},
        {"name": "stage1_long", "minutes": 3.3},
        {"name": "stage2_final", "minutes": 4.5},
    ]
    stage_preview = [
        {"name": "stage0_relevance", "approx_solver_steps": 210.0},
        {"name": "stage1_long", "approx_solver_steps": 2000.0},
        {"name": "stage2_final", "approx_solver_steps": 15000.0},
    ]
    stage_csvs = [
        ("stage0_relevance", prev_csv),
        ("stage1_long", stage1 / "stage_01.csv"),
    ]

    cap = estimate_stage_seed_cap(
        stage_idx=1,
        stage_plan=stage_plan,
        stage_preview=stage_preview,
        stage_csvs=stage_csvs,
    )
    assert cap == 1


def test_r31bf_worker_source_updates_progress_during_baseline_and_seed_prelude() -> None:
    src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "opt_worker_v3_margins_energy.py").read_text(encoding="utf-8")
    assert 'write_live_progress("baseline_done"' in src
    assert 'write_live_progress("seed_eval"' in src
    assert 'if time.time() >= t_limit:' in src
    assert 'if args.stop_file and os.path.exists(args.stop_file):' in src
