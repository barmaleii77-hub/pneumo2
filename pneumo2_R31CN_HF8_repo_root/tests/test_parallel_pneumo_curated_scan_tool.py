from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_parallel_pneumo_curated_scan_runs_as_module_help() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.parallel_pneumo_curated_scan", "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Parallel compute-only curated scan for pneumatic tuning" in proc.stdout
    assert "--candidate-json" in proc.stdout


def test_parallel_pneumo_curated_scan_runs_as_script_help() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "parallel_pneumo_curated_scan.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Parallel compute-only curated scan for pneumatic tuning" in proc.stdout
    assert "--best-json" in proc.stdout


def test_parallel_pneumo_curated_scan_creates_outputs_from_candidate_json(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidates.json"
    candidate_json.write_text(
        json.dumps(
            [
                {"name": "baseline", "overrides": {}},
                {
                    "name": "test_variant",
                    "overrides": {
                        "диаметр_поршня_Ц1": 0.045,
                        "диаметр_поршня_Ц2": 0.05,
                        "ход_штока_Ц1_перед_м": 0.30,
                        "ход_штока_Ц1_зад_м": 0.30,
                        "ход_штока_Ц2_перед_м": 0.30,
                        "ход_штока_Ц2_зад_м": 0.30,
                        "давление_Pmin_сброс": 601325.0,
                        "давление_Pmid_сброс": 851325.0,
                    },
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out_csv = tmp_path / "nested" / "scan.csv"
    best_json = tmp_path / "nested" / "best.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.parallel_pneumo_curated_scan",
            "--candidate-json",
            str(candidate_json),
            "--antiphase-only",
            "--workers",
            "2",
            "--antiphase-t-end",
            "0.6",
            "--out-csv",
            str(out_csv),
            "--best-json",
            str(best_json),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert out_csv.exists()
    assert best_json.exists()
    df = pd.read_csv(out_csv)
    assert {"name", "score", "diag_to_exhaust_ratio", "stroke_min", "stroke_max"}.issubset(df.columns)
    best = json.loads(best_json.read_text(encoding="utf-8"))
    assert isinstance(best, dict)
