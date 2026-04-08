from __future__ import annotations

import csv
import json
from pathlib import Path

from pneumo_solver_ui.optimization_run_history import summarize_run_packaging_snapshot


def test_packaging_snapshot_reads_flat_results_csv(tmp_path: Path) -> None:
    path = tmp_path / "results_all.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "anim_export_packaging_status",
                "anim_export_packaging_truth_ready",
                "верификация_флаги",
                "число_runtime_fallback_пружины",
                "число_пересечений_пружина_цилиндр",
                "число_пересечений_пружина_пружина",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "anim_export_packaging_status": "complete",
                "anim_export_packaging_truth_ready": "1",
                "верификация_флаги": "",
                "число_runtime_fallback_пружины": "0",
                "число_пересечений_пружина_цилиндр": "0",
                "число_пересечений_пружина_пружина": "0",
            }
        )
        writer.writerow(
            {
                "anim_export_packaging_status": "shared_axle_fallback",
                "anim_export_packaging_truth_ready": "0",
                "верификация_флаги": "spring_pair_clearance",
                "число_runtime_fallback_пружины": "1",
                "число_пересечений_пружина_цилиндр": "0",
                "число_пересечений_пружина_пружина": "1",
            }
        )

    snapshot = summarize_run_packaging_snapshot(path)

    assert snapshot.rows_considered == 2
    assert snapshot.rows_with_packaging == 2
    assert snapshot.packaging_complete_rows == 1
    assert snapshot.packaging_truth_ready_rows == 1
    assert snapshot.packaging_verification_pass_rows == 1
    assert snapshot.runtime_fallback_rows == 1
    assert snapshot.spring_host_interference_rows == 0
    assert snapshot.spring_pair_interference_rows == 1


def test_packaging_snapshot_reads_metrics_json_from_coordinator_trials_csv(tmp_path: Path) -> None:
    path = tmp_path / "trials.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["status", "metrics_json"],
        )
        writer.writeheader()
        writer.writerow({"status": "ERROR", "metrics_json": ""})
        writer.writerow(
            {
                "status": "DONE",
                "metrics_json": json.dumps(
                    {
                        "anim_export_packaging_status": "complete",
                        "anim_export_packaging_truth_ready": True,
                        "верификация_флаги": "",
                        "число_runtime_fallback_пружины": 0,
                        "число_пересечений_пружина_цилиндр": 1,
                        "число_пересечений_пружина_пружина": 0,
                    },
                    ensure_ascii=False,
                ),
            }
        )

    snapshot = summarize_run_packaging_snapshot(path)

    assert snapshot.rows_considered == 1
    assert snapshot.rows_with_packaging == 1
    assert snapshot.packaging_complete_rows == 1
    assert snapshot.packaging_truth_ready_rows == 1
    assert snapshot.packaging_verification_pass_rows == 1
    assert snapshot.spring_host_interference_rows == 1
    assert snapshot.spring_pair_interference_rows == 0
