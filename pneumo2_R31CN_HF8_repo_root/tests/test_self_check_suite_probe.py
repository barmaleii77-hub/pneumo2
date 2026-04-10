from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui import self_check
from pneumo_solver_ui.module_loading import load_python_module_from_path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_suite_type_probe_enables_rows_without_mutating_original() -> None:
    rows = [
        {"имя": "a", "включен": False, "тип": "микро_синфаза"},
        {"имя": "b", "включен": False, "тип": "комбо_ay3_плюс_микро"},
    ]
    probe = self_check._build_suite_type_probe_rows(rows)
    assert all(bool(row["включен"]) is True for row in probe)
    assert all(bool(row["включен"]) is False for row in rows)


def test_shipped_default_suite_type_probe_builds_combo_test() -> None:
    worker = load_python_module_from_path(UI_ROOT / "opt_worker_v3_margins_energy.py", "worker_selfcheck_probe")
    suite = json.loads((UI_ROOT / "default_suite.json").read_text(encoding="utf-8"))
    tests = worker.build_test_suite({"suite": self_check._build_suite_type_probe_rows(suite)})
    names = [str(t[0]) for t in tests]
    assert names
    assert any("комбо" in name for name in names)
