from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_root_cause_report_direct_script_uses_probe_suite_and_writes_rows(tmp_path: Path) -> None:
    base_path = tmp_path / "base.json"
    suite_path = tmp_path / "suite.json"
    model_path = tmp_path / "fake_model.py"
    worker_path = tmp_path / "fake_worker.py"
    out_prefix = tmp_path / "reports" / "root_cause_probe"

    base_path.write_text("{}", encoding="utf-8")
    suite_path.write_text(
        json.dumps(
            [
                {
                    "имя": "missing_workspace_case",
                    "включен": False,
                    "road_csv": "workspace/scenarios/missing.csv",
                },
                {
                    "имя": "probe_case",
                    "включен": False,
                    "dt": 0.02,
                    "t_end": 0.04,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    model_path.write_text("VALUE = 1\n", encoding="utf-8")
    worker_path.write_text(
        "\n".join(
            [
                "def build_test_suite(cfg):",
                "    suite = list((cfg or {}).get('suite') or [])",
                "    tests = []",
                "    for row in suite:",
                "        if bool(row.get('enabled', row.get('включен', True))):",
                "            tests.append((row.get('имя', 'case'), {'описание': 'probe'}, float(row.get('dt', 0.01)), float(row.get('t_end', 0.02)), {}))",
                "    if tests:",
                "        return tests",
                "    return [('builtin_case', {'описание': 'builtin'}, 0.01, 0.02, {})]",
                "",
                "def eval_candidate_once(model, base, test, dt, t_end, targets):",
                "    return {",
                "        'крен_max_град': 0.0,",
                "        'тангаж_max_град': 0.0,",
                "        'RMS_ускор_рамы_м_с2': 0.0,",
                "        'доля_времени_отрыв': 0.0,",
                "        'мин_запас_до_упора_штока_все_м': 0.1,",
                "        'макс_скорость_штока_все_м_с': 0.2,",
                "        'причины_нарушений': '',",
                "        'причины_физика': '',",
                "        'топ_нарушение': '',",
                "        'топ_нарушение_оценка': 0.0,",
                "    }",
                "",
                "def candidate_penalty(metrics, targets):",
                "    return 0.0",
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(UI_ROOT / "root_cause_report.py"),
            "--base",
            str(base_path),
            "--suite",
            str(suite_path),
            "--model",
            str(model_path),
            "--worker",
            str(worker_path),
            "--out",
            str(out_prefix),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "forced-enable probe copy" in proc.stdout
    assert "skipped 1 probe rows" in proc.stdout

    csv_path = Path(str(out_prefix) + ".csv")
    md_path = Path(str(out_prefix) + ".md")
    assert csv_path.exists()
    assert md_path.exists()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["тест"] == "probe_case"
    assert float(rows[0]["штраф"]) == 0.0
