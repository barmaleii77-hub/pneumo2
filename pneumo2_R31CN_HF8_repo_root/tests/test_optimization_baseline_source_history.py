from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.optimization_baseline_source import write_baseline_source_artifact
from pneumo_solver_ui.optimization_run_history import (
    format_run_choice,
    summarize_optimization_run,
)


def test_run_history_reads_staged_baseline_source_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "p_stage_demo"
    run_dir.mkdir(parents=True)
    (run_dir / "sp.json").write_text(
        '{"status": "done", "ts": "2026-04-10 14:00:00", "combined_csv": ""}',
        encoding="utf-8",
    )
    (run_dir / "results_all.csv").write_text("id,val\n1,2\n", encoding="utf-8")
    write_baseline_source_artifact(
        run_dir,
        {
            "version": "baseline_source_v1",
            "source_kind": "scoped",
            "source_label": "scoped baseline",
            "baseline_path": "C:/workspace/baselines/by_problem/p_demo/baseline_best.json",
        },
    )

    summary = summarize_optimization_run(run_dir)

    assert summary is not None
    assert summary.baseline_source_kind == "scoped"
    assert summary.baseline_source_label == "scoped baseline"
    assert summary.baseline_source_path == Path("C:/workspace/baselines/by_problem/p_demo/baseline_best.json")
    assert "base=scoped" in format_run_choice(summary)


def test_run_history_reads_coordinator_baseline_source_artifact(tmp_path: Path) -> None:
    run_dir = tmp_path / "p_coord_demo"
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True)
    (run_dir / "coordinator.log").write_text("started\n", encoding="utf-8")
    (export_dir / "trials.csv").write_text("trial_id,status,error_text\n1,DONE,\n", encoding="utf-8")
    write_baseline_source_artifact(
        run_dir,
        {
            "version": "baseline_source_v1",
            "source_kind": "global",
            "source_label": "global baseline fallback",
            "baseline_path": "C:/workspace/baselines/baseline_best.json",
        },
    )

    summary = summarize_optimization_run(run_dir)

    assert summary is not None
    assert summary.baseline_source_kind == "global"
    assert summary.baseline_source_label == "global baseline fallback"
    assert summary.baseline_source_path == Path("C:/workspace/baselines/baseline_best.json")
    assert "base=global" in format_run_choice(summary)
