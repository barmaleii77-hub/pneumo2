from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
    build_active_runtime_summary,
)


class _FakeProc:
    def __init__(self, poll_result=None) -> None:
        self._poll_result = poll_result

    def poll(self):
        return self._poll_result


def test_active_runtime_summary_reads_progress_and_trial_health(tmp_path: Path) -> None:
    run_dir = tmp_path / "coord_run"
    source_run = tmp_path / "staged_source"
    handoff_dir = source_run / "coordinator_handoff"
    export_dir = run_dir / "export"
    handoff_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    log_path = run_dir / "coordinator.log"
    log_path.write_text("hello\ndone=5/84\ntrial=5 status=RUNNING\n", encoding="utf-8")
    (export_dir / "run_scope.json").write_text(
        json.dumps(
            {
                "objective_keys": ["comfort", "energy"],
                "penalty_key": "penalty_total",
                "penalty_tol": 0.25,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (export_dir / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["trial_id", "status", "error_text", "g_json", "y_json", "metrics_json"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trial_id": "1",
                "status": "DONE",
                "error_text": "",
                "g_json": json.dumps([-0.25], ensure_ascii=False),
                "y_json": json.dumps([0.8, 1.8], ensure_ascii=False),
                "metrics_json": json.dumps(
                    {"comfort": 0.8, "energy": 1.8, "penalty_total": 0.0},
                    ensure_ascii=False,
                ),
            }
        )
        writer.writerow(
            {
                "trial_id": "2",
                "status": "DONE",
                "error_text": "",
                "g_json": json.dumps([0.35], ensure_ascii=False),
                "y_json": json.dumps([1.5, 5.3], ensure_ascii=False),
                "metrics_json": json.dumps(
                    {"comfort": 1.5, "energy": 5.3, "penalty_total": 0.6},
                    ensure_ascii=False,
                ),
            }
        )
        writer.writerow({"trial_id": "3", "status": "RUNNING", "error_text": "", "g_json": "", "y_json": "", "metrics_json": ""})
        writer.writerow({"trial_id": "4", "status": "ERROR", "error_text": "bad physics", "g_json": "", "y_json": "", "metrics_json": ""})
        writer.writerow(
            {
                "trial_id": "5",
                "status": "ERROR",
                "error_text": "solver diverged badly on wheel hop",
                "g_json": "",
                "y_json": "",
                "metrics_json": "",
            }
        )
        writer.writerow({"trial_id": "6", "status": "ERROR", "error_text": "bad physics", "g_json": "", "y_json": "", "metrics_json": ""})
    (handoff_dir / "coordinator_handoff_plan.json").write_text(
        json.dumps(
            {
                "recommended_backend": "ray",
                "recommended_proposer": "portfolio",
                "recommended_q": 2,
                "recommended_budget": 84,
                "seed_count": 6,
                "suite_analysis": {"family": "auto_ring"},
                "requires_full_ring_validation": True,
                "recommendation_reason": {
                    "fragment_count": 4,
                    "has_full_ring": True,
                    "pipeline_hint": "staged_then_coordinator",
                    "seed_bridge": {
                        "staged_rows_ok": 9,
                        "promotable_rows": 7,
                        "unique_param_candidates": 6,
                        "selection_pool": "promotable",
                        "seed_count": 6,
                    },
                },
                "cmd_args": [
                    "--backend",
                    "ray",
                    "--run-dir",
                    str(run_dir),
                    "--proposer",
                    "portfolio",
                    "--q",
                    "2",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    job = SimpleNamespace(
        proc=_FakeProc(None),
        run_dir=run_dir,
        log_path=log_path,
        budget=84,
        backend="Handoff/ray/portfolio/q2",
        pipeline_mode="coordinator",
    )

    summary = build_active_runtime_summary(
        job,
        tail_file_text_fn=lambda path: Path(path).read_text(encoding="utf-8"),
        parse_done_from_log_fn=lambda text: 5 if "done=5/84" in text else None,
        active_launch_context={
            "kind": "handoff",
            "run_dir": str(run_dir.resolve()),
            "source_run_dir": str(source_run.resolve()),
        },
    )

    assert summary["run_dir"] == str(run_dir.resolve())
    assert summary["done"] == 5
    assert summary["budget"] == 84
    assert summary["tail_state"] == "trial=5 status=RUNNING"
    assert summary["trial_health"] == {"done": 2, "running": 1, "error": 3}
    assert summary["penalty_gate"] == {
        "infeasible_done": 1,
        "penalty_key": "penalty_total",
        "penalty_tol": 0.25,
        "last_trial_id": "2",
        "last_penalty": 0.6,
        "last_objective_values": {"comfort": 1.5, "energy": 5.3},
        "objective_drift": {"comfort": 0.7, "energy": 3.5},
    }
    assert summary["recent_errors"] == [
        "bad physics",
        "solver diverged badly on wheel hop",
    ]
    assert summary["handoff_provenance"] == {
        "source_run_dir": str(source_run.resolve()),
        "source_run_name": "staged_source",
        "preset_tag": "ray/portfolio/q2",
        "selection_pool": "promotable",
        "seed_count": 6,
        "unique_param_candidates": 6,
        "promotable_rows": 7,
        "staged_rows_ok": 9,
        "pipeline_hint": "staged_then_coordinator",
        "fragment_count": 4,
        "has_full_ring": True,
    }
    assert active_runtime_progress_caption(summary) == "Active progress: done=5 / 84; tail=trial=5 status=RUNNING"
    assert active_runtime_trial_health_caption(summary) == "Trial health: DONE=2, RUNNING=1, ERROR=3."
    assert (
        active_runtime_penalty_gate_caption(summary)
        == "Penalty gate: infeasible DONE=1; last `penalty_total`=0.6 > 0.25; drift vs feasible best: comfort +0.7, energy +3.5."
    )
    assert (
        active_runtime_recent_errors_caption(summary)
        == "Recent trial errors: bad physics | solver diverged badly on wheel hop"
    )
    assert (
        active_handoff_provenance_caption(summary)
        == "Handoff provenance: source=staged_source; pool=promotable; seeds=6 from 6 unique / 7 promotable / 9 valid; pipeline=staged_then_coordinator; fragments=4; full-ring=yes."
    )


def test_active_runtime_summary_maps_cached_reserved_and_failed_trial_statuses(tmp_path: Path) -> None:
    run_dir = tmp_path / "coord_aliases"
    export_dir = run_dir / "export"
    export_dir.mkdir(parents=True)
    log_path = run_dir / "coordinator.log"
    log_path.write_text("done=1/4\n", encoding="utf-8")

    with (export_dir / "trials.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["trial_id", "status", "error_text", "g_json", "y_json", "metrics_json"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "trial_id": "1",
                "status": "CACHED",
                "error_text": "",
                "g_json": "[]",
                "y_json": "[1.0]",
                "metrics_json": '{"comfort": 1.0, "penalty_total": 0.0}',
            }
        )
        writer.writerow({"trial_id": "2", "status": "RESERVED", "error_text": "", "g_json": "", "y_json": "", "metrics_json": ""})
        writer.writerow({"trial_id": "3", "status": "FAILED", "error_text": "worker timeout", "g_json": "", "y_json": "", "metrics_json": ""})

    job = SimpleNamespace(
        proc=_FakeProc(None),
        run_dir=run_dir,
        log_path=log_path,
        budget=4,
        backend="ray",
        pipeline_mode="coordinator",
    )

    summary = build_active_runtime_summary(
        job,
        tail_file_text_fn=lambda path: Path(path).read_text(encoding="utf-8"),
        parse_done_from_log_fn=lambda text: 1 if "done=1/4" in text else None,
    )

    assert summary["trial_health"] == {"done": 1, "running": 1, "error": 1}
    assert summary["recent_errors"] == ["worker timeout"]
