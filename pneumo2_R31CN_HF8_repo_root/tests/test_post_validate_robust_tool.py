from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_post_validate_robust_runs_as_module_help() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pneumo_solver_ui.tools.post_validate_robust", "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Robust post-validation over long-suite" in proc.stdout
    assert "--results_csv" in proc.stdout


def test_post_validate_robust_runs_as_script_help() -> None:
    script = ROOT / "pneumo_solver_ui" / "tools" / "post_validate_robust.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Robust post-validation over long-suite" in proc.stdout
    assert "--results_csv" in proc.stdout


def test_post_validate_robust_creates_nested_output_and_avoids_runtime_warning(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            [
                {
                    "имя": "микро_синфаза_probe",
                    "включен": True,
                    "тип": "микро_синфаза",
                    "dt": 0.01,
                    "t_end": 0.05,
                    "A": 0.001,
                    "f_hz": 1.0,
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    results_path = tmp_path / "results.csv"
    with results_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "штраф_физичности_сумма"])
        writer.writeheader()
        writer.writerow({"id": 1, "штраф_физичности_сумма": 0.0})

    out_csv = tmp_path / "nested" / "report.csv"
    env = dict(**subprocess.os.environ)
    env["PYTHONWARNINGS"] = "error::RuntimeWarning"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.post_validate_robust",
            "--results_csv",
            str(results_path),
            "--suite_json",
            str(suite_path),
            "--base_json",
            str(ROOT / "pneumo_solver_ui" / "default_base.json"),
            "--model_path",
            str(ROOT / "pneumo_solver_ui" / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py"),
            "--top_k",
            "1",
            "--out_csv",
            str(out_csv),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert out_csv.exists()
    rows = out_csv.read_text(encoding="utf-8")
    assert "robust_total" in rows
